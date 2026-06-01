"""Unit tests for streamlit-free helpers in :mod:`crc_lib`.

The functions under test are pure-Python wrappers around ``crcglot`` plus
some local formatting / parsing utilities.  We don't re-test crcglot's
own correctness here -- crcglot has its own test suite covering the
algorithm catalog and code generation.  These tests cover the *shape*
of our wrappers: that they call crcglot correctly, normalize the
results to the renderer-friendly tuples we ship to ui.py, and reject
malformed input the way the UI expects.
"""
from __future__ import annotations

import pytest

from crc_lib import (
    ALGORITHMS,
    LANGUAGES,
    _human_separator,
    available_variants,
    detect_chunk,
    encode_int,
    padding_pills,
    parse_hex,
    parse_hex_bytes,
)


# ---------- parse_hex (single integer field) ----------

class TestParseHex:
    """Single-int hex parsing for custom-parameter form fields."""

    @pytest.mark.parametrize("raw,width,expected", [
        ("0xFF", 8, 0xFF),
        ("0XFF", 8, 0xFF),  # uppercase prefix
        ("ff", 8, 0xFF),
        ("FF", 8, 0xFF),
        (" 0xCBF43926 ", 32, 0xCBF43926),  # whitespace strip
        ("0", 8, 0),
        ("0x00", 8, 0),
    ])
    def test_valid(self, raw, width, expected):
        v, err = parse_hex(raw, "TestField", width)
        assert err is None
        assert v == expected

    def test_empty_input(self):
        v, err = parse_hex("", "Poly", 32)
        assert v is None
        assert err == "Poly is required."

    def test_whitespace_only(self):
        v, err = parse_hex("   ", "Init", 8)
        assert v is None
        assert "required" in err

    def test_not_hex(self):
        v, err = parse_hex("not-a-hex", "Xorout", 32)
        assert v is None
        assert "not a valid hex integer" in err

    def test_overflow(self):
        # 9 nibbles = 36 bits, exceeds width=32
        v, err = parse_hex("0x1FFFFFFFF", "Poly", 32)
        assert v is None
        assert "exceeds width" in err
        assert "32" in err

    def test_negative_rejected(self):
        # int("-1", 16) succeeds in Python but we expect the negative check
        v, err = parse_hex("-1", "Init", 16)
        assert v is None
        assert "non-negative" in err

    def test_at_max_width_accepted(self):
        # Exact mask value should be accepted at the boundary
        v, err = parse_hex("0xFFFFFFFF", "Poly", 32)
        assert err is None
        assert v == 0xFFFFFFFF


# ---------- parse_hex_bytes (hex-dump to bytes) ----------

class TestParseHexBytes:
    """Hex-dump → bytes for Calc tab Hex input mode and similar."""

    @pytest.mark.parametrize("raw,expected", [
        ("", b""),
        ("DEADBEEF", b"\xDE\xAD\xBE\xEF"),
        ("de ad be ef", b"\xDE\xAD\xBE\xEF"),
        ("DE AD BE EF", b"\xDE\xAD\xBE\xEF"),
        ("0xDE,0xAD,0xBE,0xEF", b"\xDE\xAD\xBE\xEF"),
        ("DE:AD:BE:EF", b"\xDE\xAD\xBE\xEF"),
        ("0xCA 0xFE", b"\xCA\xFE"),
        ("  \t \n  ", b""),  # only separators -> empty
        ("DE\nAD\nBE\nEF", b"\xDE\xAD\xBE\xEF"),  # newline separator
    ])
    def test_strip_and_decode(self, raw, expected):
        assert parse_hex_bytes(raw) == expected

    def test_non_hex_character_raises(self):
        with pytest.raises(ValueError, match="Non-hex character"):
            parse_hex_bytes("DE AD BX EF")  # 'X' not in 0-9a-f

    def test_odd_nibbles_raises(self):
        with pytest.raises(ValueError, match="odd number of nibbles"):
            parse_hex_bytes("DEADBEE")  # 7 nibbles


# ---------- _human_separator ----------

class TestHumanSeparator:
    """Pretty-name whitespace separators for the Sep pill."""

    @pytest.mark.parametrize("sep,expected", [
        ("", "NONE"),
        (" ", "SPACE"),
        ("\t", "TAB"),
        ("\n", "NEWLINE"),
        ("\r\n", "CRLF"),
        ("  ", "2 SPACES"),
        ("   ", "3 SPACES"),
        ("\t\t", "2 TABS"),
        (":", "`:`"),     # punctuation rendered as inline code
        (",", "`,`"),
        (", ", "`, `"),   # mixed whitespace + punctuation: not pure ws
    ])
    def test_humanize(self, sep, expected):
        assert _human_separator(sep) == expected


# ---------- padding_pills ----------

class TestPaddingPills:
    """Pill (label, help) tuples from a DetectMatch.padding."""

    def test_none_padding_returns_empty(self):
        assert padding_pills(None) == []

    def test_text_format_yields_three_pills(self):
        # Run detect_chunk to get a real TextFormat from crcglot
        hits = detect_chunk("123456789 0xCBF43926", mode="text")
        assert hits, "expected a text-mode match for the well-known crc32 case"
        _, _, padding = hits[0]
        pills = padding_pills(padding)
        labels = [label for label, _help in pills]
        assert labels == ["Sep: SPACE", "Prefix: 0x", "Hex: Upper"]
        # Each pill carries help text we can display
        for label, help_md in pills:
            assert help_md and isinstance(help_md, str)

    def test_text_format_lowercase_hex(self):
        hits = detect_chunk("123456789 cbf43926", mode="text")
        assert hits
        _, _, padding = hits[0]
        labels = [label for label, _help in padding_pills(padding)]
        # No prefix in this input -> no Prefix pill
        assert "Prefix: 0x" not in labels
        assert "Hex: Lower" in labels


# ---------- detect_chunk ----------

class TestDetectChunk:
    """Thin wrapper around crcglot.detect for the reverse-lookup paths."""

    # End-of-data, text mode

    def test_text_mode_classic_framing(self):
        # crc32 of b"123456789" with space + 0x prefix
        hits = detect_chunk("123456789 0xCBF43926", mode="text", width=32)
        assert [(i.name, e) for i, e, _ in hits] == [("crc32", "Big")]

    def test_text_mode_lowercase_no_prefix(self):
        hits = detect_chunk("123456789 cbf43926", mode="text")
        assert any(info.name == "crc32" for info, _, _ in hits)

    def test_text_mode_width_filter_narrows(self):
        # Same input that matches crc16-modbus at width 16
        hits = detect_chunk("1234567890 0xC20A", mode="text", width=16)
        assert {i.name for i, _, _ in hits} == {"crc16-modbus"}

    def test_text_mode_width_filter_excludes(self):
        # Width 32 filter should not find the crc16-modbus 16-bit match
        hits = detect_chunk("1234567890 0xC20A", mode="text", width=32)
        assert hits == []

    # End-of-data, hex mode

    def test_hex_mode_packed_bytes(self):
        # "313233...cbf43926" is hex-encoded "123456789" + BE crc32 bytes
        hits = detect_chunk("313233343536373839cbf43926", mode="hex")
        assert any(info.name == "crc32" for info, _, _ in hits)

    def test_hex_mode_with_colon_separator(self):
        hits = detect_chunk(
            "31:32:33:34:35:36:37:38:39:CB:F4:39:26", mode="hex"
        )
        assert any(info.name == "crc32" for info, _, _ in hits)

    # End-of-data, binary

    def test_binary_mode_be(self):
        hits = detect_chunk(b"123456789\xCB\xF4\x39\x26")
        assert any(i.name == "crc32" for i, _, _ in hits)

    def test_binary_mode_le_byte_reversed(self):
        # Byte-reversed trailing CRC -- the trailing-bytes path tries both
        # endians by default and labels the LE match as 'Little'.
        hits = detect_chunk(b"123456789\x26\x39\xF4\xCB")
        assert ("crc32", "Little") in [(i.name, e) for i, e, _ in hits]

    # Target mode

    def test_target_mode_be_match(self):
        hits = detect_chunk(b"123456789", target_crc=0xCBF43926)
        assert [(i.name, e) for i, e, _ in hits] == [("crc32", "Big")]

    def test_target_mode_le_match(self):
        # The 0.9.1 symmetry fix: byte-reversed target also matches
        hits = detect_chunk(b"123456789", target_crc=0x2639F4CB)
        assert [(i.name, e) for i, e, _ in hits] == [("crc32", "Little")]

    def test_target_mode_no_match(self):
        hits = detect_chunk(b"123456789", target_crc=0xDEADBEEF)
        assert hits == []


# ---------- available_variants ----------

class TestAvailableVariants:
    """Defer to crcglot's LanguageInfo.variants_for_width."""

    def test_c_at_width_32_includes_slice8(self):
        # C supports all three variants at width 32
        v = available_variants("c", 32)
        assert v == ["bitwise", "table", "slice8"]

    def test_c_at_width_16_excludes_slice8(self):
        # slice8 only applies at widths 32/64
        v = available_variants("c", 16)
        assert v == ["bitwise", "table"]

    def test_python_never_slice8(self):
        # Python doesn't declare slice8 support
        assert "slice8" not in available_variants("python", 32)
        assert "slice8" not in available_variants("python", 64)

    def test_vhdl_only_bitwise(self):
        # HDL targets only ship bitwise generators
        for width in (8, 16, 32, 64):
            assert available_variants("vhdl", width) == ["bitwise"]

    def test_returns_list_not_tuple(self):
        # crcglot's variants_for_width returns a tuple; our wrapper
        # converts to list so the renderer's existing code that uses
        # list operations doesn't break.
        result = available_variants("c", 32)
        assert isinstance(result, list)


# ---------- Catalog data sanity ----------

class TestCatalog:
    """Spot checks on the re-exported catalog the UI depends on."""

    def test_catalog_size_after_alias_cleanup(self):
        # crcglot 0.8.x removed the two single-letter aliases (crc16m,
        # crc16x).  The UI advertises len(ALGORITHMS) throughout, so
        # any future catalog growth is auto-picked-up -- but a sudden
        # shrink would be worth investigating.
        assert len(ALGORITHMS) == 69

    def test_aliases_not_present(self):
        # The two deleted aliases that confused the reverse-lookup UI
        assert "crc16m" not in ALGORITHMS
        assert "crc16x" not in ALGORITHMS

    def test_crc32_check_value(self):
        # Canonical check value -- if this changes, something is very wrong
        assert ALGORITHMS["crc32"].check == 0xCBF43926

    def test_encode_int_matches_check(self):
        # Sanity-check the crcglot deferral path our Calc tab uses
        assert encode_int(b"123456789", "crc32") == ALGORITHMS["crc32"].check

    def test_languages_present(self):
        # The eight languages the README and UI advertise
        expected = {"c", "csharp", "go", "python", "rust", "typescript", "verilog", "vhdl"}
        assert expected <= set(LANGUAGES.keys())
