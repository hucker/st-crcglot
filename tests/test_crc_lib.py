"""Unit tests for the streamlit-free helpers in :mod:`crc_lib`.

Scope rule of thumb: a test belongs here if it would fail when *our*
wrapper code breaks, but would pass when only crcglot's internals
change (and vice versa).  That means we explicitly *don't* re-test
crcglot's catalogue contents, algorithm correctness, or framing
detection -- crcglot has its own test suite covering all of that, and
duplicating it here just inflates the test count without catching
bugs in *our* code.

What we do test:

- The parsing helpers (``parse_hex``, ``parse_hex_bytes``,
  ``_human_separator``) -- pure Python utilities owned entirely by us.
- The translation our wrappers do on the way out of crcglot:
  ``detect_chunk`` normalizing ``"big"``/``"little"`` to
  ``"Big"``/``"Little"``, picking the mode from input type when the
  caller doesn't specify, and translating ``width`` into the
  ``crc<W>*`` algorithm glob.
- ``padding_pills`` formatting both ``TextFormat`` and ``HexFormat``
  into the pill-ready ``(label, help)`` tuples the renderer consumes.
"""

from __future__ import annotations

import pytest

from crc_lib import (
    _human_separator,
    available_variants,
    detect_chunk,
    padding_pills,
    parse_hex,
    parse_hex_bytes,
)


# ---------- parse_hex (single integer field) ----------


class TestParseHex:
    """Boundary tests for the custom-parameter form field parser."""

    @pytest.mark.parametrize(
        "raw,width,expected",
        [
            ("0xFF", 8, 0xFF),
            ("0XFF", 8, 0xFF),
            ("ff", 8, 0xFF),
            ("FF", 8, 0xFF),
            (" 0xCBF43926 ", 32, 0xCBF43926),
            ("0", 8, 0),
        ],
    )
    def test_valid(self, raw, width, expected):
        v, err = parse_hex(raw, "TestField", width)
        assert err is None
        assert v == expected

    def test_empty_input(self):
        v, err = parse_hex("", "Poly", 32)
        assert v is None
        assert err == "Poly is required."

    def test_not_hex(self):
        v, err = parse_hex("not-a-hex", "Xorout", 32)
        assert v is None
        assert err is not None and "not a valid hex integer" in err

    def test_overflow_caught(self):
        # 33-bit value doesn't fit in width=32
        v, err = parse_hex("0x1FFFFFFFF", "Poly", 32)
        assert v is None
        assert err is not None and "exceeds width" in err

    def test_negative_caught(self):
        v, err = parse_hex("-1", "Init", 16)
        assert v is None
        assert err is not None and "non-negative" in err

    def test_exact_max_accepted(self):
        # Boundary case: the mask itself fits
        v, err = parse_hex("0xFFFFFFFF", "Poly", 32)
        assert err is None
        assert v == 0xFFFFFFFF


# ---------- parse_hex_bytes (hex-dump to bytes) ----------


class TestParseHexBytes:
    """Separator-strip + decode behavior for hex-dump pastes."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("", b""),
            ("DEADBEEF", b"\xde\xad\xbe\xef"),
            ("de ad be ef", b"\xde\xad\xbe\xef"),
            ("0xDE,0xAD,0xBE,0xEF", b"\xde\xad\xbe\xef"),
            ("DE:AD:BE:EF", b"\xde\xad\xbe\xef"),
            ("0xCA 0xFE", b"\xca\xfe"),
            ("DE\nAD\nBE\nEF", b"\xde\xad\xbe\xef"),
        ],
    )
    def test_decode(self, raw, expected):
        assert parse_hex_bytes(raw) == expected

    def test_separator_only_input_is_empty(self):
        # The Calc tab relies on this returning empty bytes (not erroring)
        # so it can show its own "empty after stripping" error instead.
        assert parse_hex_bytes("  \t \n  ") == b""

    def test_non_hex_character_raises(self):
        with pytest.raises(ValueError, match="Non-hex character"):
            parse_hex_bytes("DE AD BX EF")

    def test_odd_nibbles_raises(self):
        with pytest.raises(ValueError, match="odd number of nibbles"):
            parse_hex_bytes("DEADBEE")


# ---------- _human_separator ----------


class TestHumanSeparator:
    """The pill label for the Sep field.  Owned entirely by us."""

    def test_whitespace_named(self):
        # Each whitespace character gets a keyboard-key word
        assert _human_separator(" ") == "SPACE"
        assert _human_separator("\t") == "TAB"
        assert _human_separator("\n") == "NEWLINE"
        assert _human_separator("\r\n") == "CRLF"

    def test_empty_is_none_marker(self):
        # Reverse-lookup framing where the CRC butts directly against payload
        assert _human_separator("") == "NONE"

    def test_repeated_whitespace_is_counted(self):
        # "2 SPACES" / "3 TABS" rather than `  ` / `\t\t` in inline code
        assert _human_separator("  ") == "2 SPACES"
        assert _human_separator("\t\t\t") == "3 TABS"

    def test_punctuation_rendered_as_inline_code(self):
        # Visible characters stay literal, wrapped in markdown backticks
        assert _human_separator(":") == "`:`"
        assert _human_separator(", ") == "`, `"


# ---------- padding_pills ----------


class TestPaddingPills:
    """Boundary translation from DetectMatch.padding to pill tuples."""

    def test_none_padding_returns_empty(self):
        # Binary input and target_crc mode both produce padding=None;
        # the renderer should get zero pills (not crash, not show 'Sep:
        # NONE' as a fake label).
        assert padding_pills(None) == []

    def test_text_format_three_pills_with_prefix(self):
        # Sep + Prefix + Hex when the input has a "0x" prefix
        hits = detect_chunk("123456789 0xCBF43926", mode="text")
        _, _, padding = hits[0]
        labels = [label for label, _ in padding_pills(padding)]
        assert labels == ["Sep: SPACE", "Prefix: 0x", "Hex: Upper"]

    def test_text_format_omits_prefix_pill_when_absent(self):
        # No "0x" -> no Prefix pill (only Sep + Hex)
        hits = detect_chunk("123456789 cbf43926", mode="text")
        _, _, padding = hits[0]
        labels = [label for label, _ in padding_pills(padding)]
        assert labels == ["Sep: SPACE", "Hex: Lower"]

    def test_hex_format_pills(self):
        # Hex auto-decode mode uses HexFormat -- a different padding
        # type with its own field names (byte_separator vs separator,
        # prefix vs hex_prefix).  Our wrapper has to handle both.
        hits = detect_chunk(
            "0x31,0x32,0x33,0x34,0x35,0x36,0x37,0x38,0x39,0xcb,0xf4,0x39,0x26",
            mode="hex",
        )
        assert hits, "expected a hex-mode crc32 match for the canonical input"
        _, _, padding = hits[0]
        pills = padding_pills(padding)
        labels = [label for label, _ in pills]
        # Sep pill reflects the byte separator detected
        assert any(lbl.startswith("Sep:") for lbl in labels)
        # Prefix pill shows the "0x" prefix that was applied per-byte
        prefix_pill = [lbl for lbl in labels if lbl.startswith("Prefix:")]
        assert prefix_pill, f"expected a Prefix pill, got {labels}"
        # The wrapper appends "(per byte)" when HexFormat.prefix_per_byte
        # is True -- that distinguishes "0xDEADBEEF" (one prefix) from
        # "0xDE 0xAD 0xBE 0xEF" (per-byte prefix).
        assert "(per byte)" in prefix_pill[0]

    def test_help_text_present_for_each_pill(self):
        # Renderer expects (label, help) tuples; empty help would
        # silently render a no-op tooltip.
        hits = detect_chunk("123456789 0xCBF43926", mode="text")
        _, _, padding = hits[0]
        for label, help_md in padding_pills(padding):
            assert label and help_md
            assert isinstance(help_md, str)


# ---------- detect_chunk ----------
#
# These tests target the *wrapper*, not crcglot.  In particular: the
# translation of input type to mode (str -> "text", bytes -> "binary"),
# the translation of width int to algorithms glob, the endian-string
# casing change (crcglot's "big"/"little" -> our "Big"/"Little"), and
# the 3-tuple return shape the renderer relies on.


class TestDetectChunkShape:
    """Return-shape and normalization invariants of detect_chunk."""

    def test_returns_three_tuples_of_correct_types(self):
        hits = detect_chunk(b"123456789\xcb\xf4\x39\x26")
        assert hits  # something matched
        for item in hits:
            assert isinstance(item, tuple) and len(item) == 3
            info, endian, padding = item
            # info comes through unchanged from crcglot
            assert hasattr(info, "name") and hasattr(info, "width")
            # endian is the title-cased string we add
            assert endian in ("Big", "Little")

    def test_endian_string_is_title_cased(self):
        # crcglot returns 'big'/'little' lower-case.  Our wrapper
        # title-cases them so the renderer can drop them straight into
        # "Endian: Big" pills without further string munging.
        be = detect_chunk(b"123456789\xcb\xf4\x39\x26")
        assert be[0][1] == "Big"
        # LE-trailing crc32 -- byte-reversed CRC bytes
        le = detect_chunk(b"123456789\x26\x39\xf4\xcb")
        assert any(item[1] == "Little" for item in le)


class TestDetectChunkModeInference:
    """When the caller doesn't specify mode= explicitly, the wrapper
    picks based on input type.  This is the contract the UI relies on
    for the Hex/Text toggle."""

    def test_bytes_input_defaults_to_binary_mode(self):
        # Binary mode -> trailing bytes are the CRC; this only resolves
        # if our wrapper actually inferred mode='binary'.  If it
        # silently fell through to text mode, the test would fail.
        hits = detect_chunk(b"123456789\xcb\xf4\x39\x26")
        assert ("crc32", "Big") in [(i.name, e) for i, e, _ in hits]

    def test_str_input_defaults_to_text_mode(self):
        # Text mode -> last hex chars are the CRC; the asymmetry case
        # "1234567890 0xC20A" is the litmus test for whether mode='auto'
        # accidentally hex-decoded the string and found crc8 matches
        # instead.  Default mode inference must pick 'text' for str.
        hits = detect_chunk("1234567890 0xC20A", width=16)
        assert {i.name for i, _, _ in hits} == {"crc16-modbus"}


class TestDetectChunkWidthGlob:
    """The wrapper turns width into an algorithms glob.  Verify the
    narrowing actually narrows."""

    def test_width_filter_drops_other_widths(self):
        # crc32 of "123456789" with the well-known trailing bytes
        chunk = b"123456789\xcb\xf4\x39\x26"
        # width=32 matches
        assert any(i.name == "crc32" for i, _, _ in detect_chunk(chunk, width=32))
        # width=16 narrows it away
        assert detect_chunk(chunk, width=16) == []
        # width=None doesn't apply a filter
        assert any(i.name == "crc32" for i, _, _ in detect_chunk(chunk, width=None))


class TestDetectChunkTargetMode:
    """The target_crc kwarg flips detect's contract: packet is data
    only.  Verify our wrapper forwards target_crc untouched and that
    the 0.9.1 BE/LE symmetry is exposed."""

    def test_be_target_matched_as_big(self):
        hits = detect_chunk(b"123456789", target_crc=0xCBF43926)
        assert [(i.name, e) for i, e, _ in hits] == [("crc32", "Big")]

    def test_le_target_matched_as_little(self):
        # crcglot 0.9.1's symmetry fix: 0x2639F4CB (the byte-reversed
        # crc32 of 123456789) matches as endianness='little'.  If our
        # wrapper drops target_crc on the floor this returns nothing.
        hits = detect_chunk(b"123456789", target_crc=0x2639F4CB)
        assert [(i.name, e) for i, e, _ in hits] == [("crc32", "Little")]

    def test_padding_is_none_in_target_mode(self):
        # target_crc doesn't byte-parse, so padding is None -- means the
        # renderer shouldn't try to show Sep/Prefix/Hex pills for
        # Target-mode matches.
        hits = detect_chunk(b"123456789", target_crc=0xCBF43926)
        for _, _, padding in hits:
            assert padding is None


# ---------- available_variants ----------


class TestAvailableVariants:
    """Structural checks on the variants_for_width forwarding.  The
    actual per-language per-width data is owned by crcglot."""

    def test_returns_list_not_tuple(self):
        # crcglot returns a tuple; our wrapper widens to list so the
        # renderer can use list methods on it.  If we forget the
        # list() conversion, list-only operations (e.g. iteration with
        # for-else, mutable accumulation) would break.
        assert isinstance(available_variants("c", 32), list)

    def test_slice8_only_at_width_32_and_64_for_c(self):
        # The crcglot side of the contract -- documented in detect's
        # docstring -- is that slice8 requires width 32 or 64.  We
        # don't enforce this ourselves anymore (the magic check is
        # deleted), so this test is really verifying we *don't* drop
        # the rule on the way through.
        assert "slice8" not in available_variants("c", 8)
        assert "slice8" not in available_variants("c", 16)
        assert "slice8" in available_variants("c", 32)
        assert "slice8" in available_variants("c", 64)
