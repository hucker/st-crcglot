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

Style: every test is structured Arrange / Act / Assert (AAA), with
section-header comments and a blank line between sections.  Tests
whose arrangement is just inline literals (``_human_separator(" ")``)
use a ``# Act + Assert`` header to avoid inventing a fake Arrange.
"""

from __future__ import annotations

import pytest

from crc_lib import (
    _human_separator,
    available_variants,
    available_variants_bundle,
    detect_chunk,
    generate_catalogue,
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
        # Arrange: inputs come from the parametrize table above; the
        # expected value is the third tuple element.

        # Act
        actual_value, actual_err = parse_hex(raw, "TestField", width)

        # Assert: valid input parses cleanly with no error.
        assert actual_err is None, f"valid input {raw!r} produced error {actual_err!r}"
        assert actual_value == expected, (
            f"parse_hex({raw!r}) = {actual_value!r}, expected {expected!r}"
        )

    def test_empty_input(self):
        # Arrange
        raw = ""
        expected_err = "Poly is required."

        # Act
        actual_value, actual_err = parse_hex(raw, "Poly", 32)

        # Assert: empty input is reported as missing-required, not as malformed.
        assert actual_value is None, (
            f"empty input should not produce a value; got {actual_value!r}"
        )
        assert actual_err == expected_err, (
            f"empty-input error = {actual_err!r}, expected {expected_err!r}"
        )

    def test_not_hex(self):
        # Arrange
        raw = "not-a-hex"
        expected_err_fragment = "not a valid hex integer"

        # Act
        actual_value, actual_err = parse_hex(raw, "Xorout", 32)

        # Assert: non-hex input produces a UI-friendly error fragment.
        assert actual_value is None, (
            f"non-hex input should not produce a value; got {actual_value!r}"
        )
        assert actual_err is not None, "non-hex input should produce an error"
        assert expected_err_fragment in actual_err, (
            f"error {actual_err!r} should contain {expected_err_fragment!r}"
        )

    def test_overflow_caught(self):
        # Arrange: a 33-bit value that doesn't fit in width=32.
        raw = "0x1FFFFFFFF"
        expected_err_fragment = "exceeds width"

        # Act
        actual_value, actual_err = parse_hex(raw, "Poly", 32)

        # Assert: overflow returns None and an explanatory error.
        assert actual_value is None, (
            f"overflow should not produce a value; got {actual_value!r}"
        )
        assert actual_err is not None, "overflow should produce an error"
        assert expected_err_fragment in actual_err, (
            f"error {actual_err!r} should contain {expected_err_fragment!r}"
        )

    def test_negative_caught(self):
        # Arrange
        raw = "-1"
        expected_err_fragment = "non-negative"

        # Act
        actual_value, actual_err = parse_hex(raw, "Init", 16)

        # Assert: negative input is rejected with a clear message.
        assert actual_value is None, (
            f"negative input should not produce a value; got {actual_value!r}"
        )
        assert actual_err is not None, "negative input should produce an error"
        assert expected_err_fragment in actual_err, (
            f"error {actual_err!r} should contain {expected_err_fragment!r}"
        )

    def test_exact_max_accepted(self):
        # Arrange: the boundary value -- the mask itself.
        raw = "0xFFFFFFFF"
        expected_value = 0xFFFFFFFF

        # Act
        actual_value, actual_err = parse_hex(raw, "Poly", 32)

        # Assert: the boundary value fits within the width and parses cleanly.
        assert actual_err is None, (
            f"boundary value should parse cleanly; got error {actual_err!r}"
        )
        assert actual_value == expected_value, (
            f"parse_hex({raw!r}) = {actual_value!r}, expected {expected_value!r}"
        )


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
        # Arrange: inputs come from the parametrize table above.

        # Act
        actual = parse_hex_bytes(raw)

        # Assert: every separator variation decodes to the same bytes.
        assert actual == expected, (
            f"parse_hex_bytes({raw!r}) = {actual!r}, expected {expected!r}"
        )

    def test_separator_only_input_is_empty(self):
        # Arrange: a string of only separators (whitespace).  The Calc
        # tab relies on this returning empty bytes (not erroring) so it
        # can show its own "empty after stripping" message instead.
        raw = "  \t \n  "
        expected = b""

        # Act
        actual = parse_hex_bytes(raw)

        # Assert: separator-only inputs become empty bytes (not exceptions).
        assert actual == expected, (
            f"separator-only input should decode to {expected!r}; got {actual!r}"
        )

    def test_non_hex_character_raises(self):
        # Arrange: a hex-looking string with one non-hex char ('X').
        raw = "DE AD BX EF"

        # Act + Assert: the parser raises with a UI-friendly message.
        with pytest.raises(ValueError, match="Non-hex character"):
            parse_hex_bytes(raw)

    def test_odd_nibbles_raises(self):
        # Arrange: 7 nibbles -- odd number, can't form whole bytes.
        raw = "DEADBEE"

        # Act + Assert: the parser raises with an odd-nibble error.
        with pytest.raises(ValueError, match="odd number of nibbles"):
            parse_hex_bytes(raw)


# ---------- _human_separator ----------


class TestHumanSeparator:
    """The pill label for the Sep field.  Owned entirely by us."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            (" ", "SPACE"),
            ("\t", "TAB"),
            ("\n", "NEWLINE"),
            ("\r\n", "CRLF"),
        ],
    )
    def test_whitespace_named(self, raw, expected):
        # Arrange: inputs come from the parametrize table above.

        # Act
        actual = _human_separator(raw)

        # Assert: each whitespace character gets a keyboard-key word.
        assert actual == expected, (
            f"_human_separator({raw!r}) = {actual!r}, expected {expected!r}"
        )

    def test_empty_is_none_marker(self):
        # Arrange: reverse-lookup framing where the CRC butts directly
        # against the payload; the empty separator must render as
        # "NONE", not as an empty string.
        raw = ""
        expected = "NONE"

        # Act
        actual = _human_separator(raw)

        # Assert
        assert actual == expected, (
            f"_human_separator({raw!r}) = {actual!r}, expected {expected!r}"
        )

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("  ", "2 SPACES"),
            ("\t\t\t", "3 TABS"),
        ],
    )
    def test_repeated_whitespace_is_counted(self, raw, expected):
        # Arrange: inputs from the parametrize table.

        # Act
        actual = _human_separator(raw)

        # Assert: "2 SPACES" / "3 TABS" rather than the raw chars.
        assert actual == expected, (
            f"_human_separator({raw!r}) = {actual!r}, expected {expected!r}"
        )

    @pytest.mark.parametrize(
        "raw,expected",
        [
            (":", "`:`"),
            (", ", "`, `"),
        ],
    )
    def test_punctuation_rendered_as_inline_code(self, raw, expected):
        # Arrange: inputs from the parametrize table.

        # Act
        actual = _human_separator(raw)

        # Assert: visible characters stay literal, wrapped in markdown
        # backticks for inline-code rendering on the pill.
        assert actual == expected, (
            f"_human_separator({raw!r}) = {actual!r}, expected {expected!r}"
        )


# ---------- padding_pills ----------


class TestPaddingPills:
    """Boundary translation from DetectMatch.padding to pill tuples."""

    def test_none_padding_returns_empty(self):
        # Arrange: binary input and target_crc mode both produce
        # padding=None.  The renderer should get zero pills (not
        # crash, not show "Sep: NONE" as a fake label).
        padding = None
        expected = []

        # Act
        actual = padding_pills(padding)

        # Assert: empty list, not a placeholder pill.
        assert actual == expected, (
            f"padding_pills(None) should return {expected!r}; got {actual!r}"
        )

    def test_text_format_three_pills_with_prefix(self):
        # Arrange: drive crcglot to produce a real TextFormat with all
        # three fields populated (separator + prefix + uppercase hex).
        hits = detect_chunk("123456789 0xCBF43926", mode="text")
        _, _, _, padding = hits[0]
        expected = ["Sep: SPACE", "Prefix: 0x", "Hex: Upper"]

        # Act
        actual = [label for label, _help in padding_pills(padding)]

        # Assert: Sep + Prefix + Hex pills in fixed order.
        assert actual == expected, (
            f"text-format pills = {actual!r}, expected {expected!r}"
        )

    def test_text_format_omits_prefix_pill_when_absent(self):
        # Arrange: no "0x" -> no Prefix pill should appear.
        hits = detect_chunk("123456789 cbf43926", mode="text")
        _, _, _, padding = hits[0]
        expected = ["Sep: SPACE", "Hex: Lower"]

        # Act
        actual = [label for label, _help in padding_pills(padding)]

        # Assert: only Sep + Hex, no Prefix pill when no prefix detected.
        assert actual == expected, (
            f"no-prefix pills = {actual!r}, expected {expected!r}"
        )

    def test_hex_format_pills(self):
        # Arrange: hex auto-decode mode uses HexFormat -- a different
        # padding type with its own field names (byte_separator vs
        # separator, prefix vs hex_prefix).  Our wrapper has to handle
        # both.  The per-byte 0x-prefixed input below produces a
        # HexFormat with prefix_per_byte=True.
        hits = detect_chunk(
            "0x31,0x32,0x33,0x34,0x35,0x36,0x37,0x38,0x39,0xcb,0xf4,0x39,0x26",
            mode="hex",
        )
        assert hits, "expected a hex-mode crc32 match for the canonical input"
        _, _, _, padding = hits[0]

        # Act
        actual_pills = padding_pills(padding)
        actual_labels = [label for label, _help in actual_pills]
        actual_prefix_labels = [
            lbl for lbl in actual_labels if lbl.startswith("Prefix:")
        ]

        # Assert: HexFormat produces a Sep pill, a Prefix pill, and the
        # Prefix label carries "(per byte)" because prefix_per_byte=True
        # on this input (each byte was individually 0x-prefixed).
        assert any(lbl.startswith("Sep:") for lbl in actual_labels), (
            f"expected a Sep pill in {actual_labels!r}"
        )
        assert actual_prefix_labels, f"expected a Prefix pill in {actual_labels!r}"
        assert "(per byte)" in actual_prefix_labels[0], (
            f"Prefix pill should mark per-byte; got {actual_prefix_labels[0]!r}"
        )

    def test_help_text_present_for_each_pill(self):
        # Arrange: drive crcglot to produce a real TextFormat.
        hits = detect_chunk("123456789 0xCBF43926", mode="text")
        _, _, _, padding = hits[0]

        # Act
        actual_pills = padding_pills(padding)

        # Assert: every pill is a non-empty (label, help) tuple of strs.
        # An empty help string would silently render a no-op tooltip.
        for label, help_md in actual_pills:
            assert label, f"pill has empty label: {(label, help_md)!r}"
            assert help_md, f"pill has empty help text: {(label, help_md)!r}"
            assert isinstance(help_md, str), (
                f"pill help should be str; got {type(help_md).__name__}"
            )


# ---------- detect_chunk ----------
#
# These tests target the *wrapper*, not crcglot.  In particular: the
# translation of input type to mode (str -> "text", bytes -> "binary"),
# the translation of width int to algorithms glob, the endian-string
# casing change (crcglot's "big"/"little" -> our "Big"/"Little"), and
# the 3-tuple return shape the renderer relies on.


class TestDetectChunkShape:
    """Return-shape and normalization invariants of detect_chunk."""

    def test_returns_four_tuples_of_correct_types(self):
        # Arrange: canonical crc32 trailing-bytes binary input.
        chunk = b"123456789\xcb\xf4\x39\x26"

        # Act
        actual_hits = detect_chunk(chunk)

        # Assert: at least one match, each is a 4-tuple of
        # (name, info, endian-str, padding-or-None) -- crcglot 0.10+
        # carries the catalog name on the DetectMatch (not on info),
        # so detect_chunk surfaces it as the first element.
        assert actual_hits, f"expected a match for {chunk!r}; got nothing"
        for item in actual_hits:
            assert isinstance(item, tuple) and len(item) == 4, (
                f"each match should be a 4-tuple; got {item!r}"
            )
            name, info, endian, _padding = item
            assert isinstance(name, str) and name, (
                f"name should be a non-empty str; got {name!r}"
            )
            assert hasattr(info, "width") and hasattr(info, "source"), (
                f"info should expose width/source; got {info!r}"
            )
            assert endian in ("Big", "Little"), (
                f"endian should be 'Big'/'Little'; got {endian!r}"
            )

    def test_endian_string_is_title_cased(self):
        # Arrange: BE-trailing and LE-trailing crc32 inputs.  crcglot
        # itself returns 'big' / 'little' lower-case; our wrapper
        # title-cases them so the renderer can drop them straight into
        # "Endian: Big" pills without further string munging.
        be_chunk = b"123456789\xcb\xf4\x39\x26"
        le_chunk = b"123456789\x26\x39\xf4\xcb"
        expected_be_endian = "Big"
        expected_le_endian = "Little"

        # Act
        actual_be_hits = detect_chunk(be_chunk)
        actual_le_hits = detect_chunk(le_chunk)

        # Assert: title-cased "Big" / "Little" strings, not crcglot's
        # lower-case originals.  Endian is element [2] in the 4-tuple
        # (name, info, endian, padding).
        assert actual_be_hits[0][2] == expected_be_endian, (
            f"BE chunk endian = {actual_be_hits[0][2]!r}, "
            f"expected {expected_be_endian!r}"
        )
        assert any(item[2] == expected_le_endian for item in actual_le_hits), (
            f"LE chunk should yield at least one '{expected_le_endian}' "
            f"match; got {[item[2] for item in actual_le_hits]!r}"
        )


class TestDetectChunkModeInference:
    """When the caller doesn't specify mode= explicitly, the wrapper
    picks based on input type.  This is the contract the UI relies on
    for the Hex/Text toggle."""

    def test_bytes_input_defaults_to_binary_mode(self):
        # Arrange: bytes input -- trailing bytes are the CRC.  Resolves
        # only if our wrapper actually inferred mode='binary'.
        chunk = b"123456789\xcb\xf4\x39\x26"
        expected_match = ("crc32", "Big")

        # Act
        actual_matches = [(n, e) for n, _i, e, _ in detect_chunk(chunk)]

        # Assert: bytes input must yield the binary-mode crc32 match.
        assert expected_match in actual_matches, (
            f"bytes input should yield {expected_match!r}; got {actual_matches!r}"
        )

    def test_str_input_defaults_to_text_mode(self):
        # Arrange: the litmus case "1234567890 0xC20A".  This input
        # parses as either text or hex; mode='auto' historically hex-
        # decoded and found crc8 matches.  Default mode inference must
        # pick 'text' for str inputs.
        chunk = "1234567890 0xC20A"
        expected_names = {"crc16-modbus"}

        # Act
        actual_names = {n for n, _i, _e, _ in detect_chunk(chunk, width=16)}

        # Assert: text-mode inference yields the crc16-modbus match,
        # not the crc8 shadows that hex-mode would surface.
        assert actual_names == expected_names, (
            f"str input width=16 should yield {expected_names!r}; got {actual_names!r}"
        )


class TestDetectChunkWidthGlob:
    """The wrapper turns width into an algorithms glob.  Verify the
    narrowing actually narrows."""

    def test_width_filter_drops_other_widths(self):
        # Arrange: crc32 of "123456789" with the well-known trailing bytes.
        chunk = b"123456789\xcb\xf4\x39\x26"

        # Act
        actual_w32 = detect_chunk(chunk, width=32)
        actual_w16 = detect_chunk(chunk, width=16)
        actual_unfiltered = detect_chunk(chunk, width=None)

        # Assert: width=32 keeps the match, width=16 narrows it away,
        # width=None applies no filter and keeps the match.
        assert any(n == "crc32" for n, _i, _e, _ in actual_w32), (
            f"width=32 should yield crc32; got {[n for n, _i, _e, _ in actual_w32]!r}"
        )
        assert actual_w16 == [], (
            f"width=16 should narrow away the crc32 match; got {actual_w16!r}"
        )
        assert any(n == "crc32" for n, _i, _e, _ in actual_unfiltered), (
            f"width=None should keep crc32; "
            f"got {[n for n, _i, _e, _ in actual_unfiltered]!r}"
        )


class TestDetectChunkTargetMode:
    """The target_crc kwarg flips detect's contract: packet is data
    only.  Verify our wrapper forwards target_crc untouched and that
    the 0.9.1 BE/LE symmetry is exposed."""

    def test_be_target_matched_as_big(self):
        # Arrange: crc32 BE target.
        chunk = b"123456789"
        target = 0xCBF43926
        expected = [("crc32", "Big")]

        # Act
        actual = [(n, e) for n, _i, e, _ in detect_chunk(chunk, target_crc=target)]

        # Assert: BE target hits the crc32 algorithm with "Big" endian.
        assert actual == expected, (
            f"target_crc=0x{target:08X} should yield {expected!r}; got {actual!r}"
        )

    def test_le_target_matched_as_little(self):
        # Arrange: byte-reversed crc32 of "123456789".  crcglot 0.9.1's
        # symmetry fix means this should still match crc32, flagged as
        # endianness='little'.  If our wrapper drops target_crc on the
        # floor, this returns nothing.
        chunk = b"123456789"
        target = 0x2639F4CB
        expected = [("crc32", "Little")]

        # Act
        actual = [(n, e) for n, _i, e, _ in detect_chunk(chunk, target_crc=target)]

        # Assert: LE target also hits crc32, flagged "Little".
        assert actual == expected, (
            f"target_crc=0x{target:08X} should yield {expected!r}; got {actual!r}"
        )

    def test_padding_is_none_in_target_mode(self):
        # Arrange: target_crc mode doesn't byte-parse anything, so
        # padding is None -- which means the renderer must not try to
        # show Sep/Prefix/Hex pills for Target-mode matches.
        chunk = b"123456789"
        target = 0xCBF43926

        # Act
        actual_hits = detect_chunk(chunk, target_crc=target)

        # Assert: every Target-mode match has padding=None.
        for name, _info, endian, padding in actual_hits:
            assert padding is None, (
                f"Target-mode match for {name}/{endian} "
                f"should have padding=None; got {padding!r}"
            )


# ---------- available_variants ----------


class TestAvailableVariants:
    """Structural checks on the variants_for_width forwarding.  The
    actual per-language per-width data is owned by crcglot."""

    def test_returns_list_not_tuple(self):
        # Arrange: crcglot returns a tuple; our wrapper widens to list
        # so the renderer can use list methods on it.

        # Act
        actual = available_variants("c", 32)

        # Assert: list (not tuple) is the contract the renderer relies on.
        assert isinstance(actual, list), (
            f"available_variants should return list; got {type(actual).__name__}"
        )

    @pytest.mark.parametrize(
        "width,expected_slice8_present",
        [
            (8, False),
            (16, False),
            (32, True),
            (64, True),
        ],
    )
    def test_slice8_only_at_width_32_and_64_for_c(self, width, expected_slice8_present):
        # Arrange: width from the parametrize table.  slice8 requires
        # width 32 or 64 (crcglot's rule, documented in detect's
        # docstring).  We don't enforce this ourselves -- the magic
        # check was deleted -- so this verifies we *don't* drop the
        # rule on the way through.

        # Act
        actual_variants = available_variants("c", width)
        actual_has_slice8 = "slice8" in actual_variants

        # Assert
        assert actual_has_slice8 == expected_slice8_present, (
            f"C width={width}: slice8 present={actual_has_slice8}, "
            f"expected={expected_slice8_present}; full list {actual_variants!r}"
        )


# ---------- available_variants_bundle ----------
#
# Multi-algorithm bundles emit one variant across every algorithm, so
# our wrapper has to filter to the intersection.  These tests pin the
# intersection rule (not crcglot's per-width lists, which it owns).


class TestAvailableVariantsBundle:
    """Intersection-of-widths variant filtering for bundle mode."""

    def test_bundle_drops_slice8_when_any_width_is_narrow(self):
        # Arrange: mixing an 8-bit CRC with a 32-bit CRC.  slice8 is
        # valid for 32 (alone) but invalid for 8, so the bundle picker
        # must NOT offer slice8.
        widths = [8, 32]
        unexpected = "slice8"

        # Act
        actual_variants = available_variants_bundle("c", widths)

        # Assert: slice8 dropped, bitwise + table still present.
        assert unexpected not in actual_variants, (
            f"bundle with widths {widths} should not offer {unexpected!r}; "
            f"got {actual_variants!r}"
        )
        assert "bitwise" in actual_variants, (
            f"bundle should always include bitwise; got {actual_variants!r}"
        )

    def test_bundle_keeps_slice8_when_all_widths_support_it(self):
        # Arrange: 32 and 64 both support slice8, so the bundle does too.
        widths = [32, 64]
        expected = "slice8"

        # Act
        actual_variants = available_variants_bundle("c", widths)

        # Assert: slice8 present in the intersection.
        assert expected in actual_variants, (
            f"bundle with widths {widths} should offer {expected!r}; "
            f"got {actual_variants!r}"
        )

    def test_empty_widths_falls_back_to_full_default_list(self):
        # Arrange: empty selection (renderer shouldn't reach the bundle
        # picker in this state, but the helper must not crash on it).

        # Act
        actual_variants = available_variants_bundle("c", [])

        # Assert: non-empty, contains bitwise at minimum.
        assert actual_variants, "empty widths should still yield variants"
        assert "bitwise" in actual_variants, (
            f"empty-widths fallback should include bitwise; got {actual_variants!r}"
        )

    def test_single_width_matches_available_variants(self):
        # Arrange: a one-width "bundle" should equal the single-algo
        # variant list -- the intersection is trivial.
        width = 32

        # Act
        actual_bundle = available_variants_bundle("c", [width])
        actual_single = available_variants("c", width)

        # Assert: identical lists in identical order (canonical order
        # is preserved by both paths).
        assert actual_bundle == actual_single, (
            f"single-width bundle {actual_bundle!r} should equal "
            f"available_variants({width}) {actual_single!r}"
        )


# ---------- generate_catalogue: multi-algorithm bundling ----------
#
# crcglot 0.12 added a per-language combiner that merges N single-algo
# outputs into one file.  Our wrapper auto-routes through it when a
# list is passed.


class TestGenerateCatalogueBundle:
    """Single-vs-list dispatch and per-language combiner shape."""

    def test_single_name_returns_string_for_java(self):
        # Arrange: Java single-algo wraps methods in a fixed `CrcGlot`
        # container class (the `symbol=` parameter becomes the method
        # name prefix, not the class name -- only the multi-algo
        # combiner names the container from the file stem).
        symbol = "MyCrc32"

        # Act
        actual = generate_catalogue("java", "crc32", "bitwise", symbol)

        # Assert: string with the default container class plus methods
        # named after the symbol prefix.
        assert isinstance(actual, str), (
            f"java single-algo should be str; got {type(actual).__name__}"
        )
        assert "public final class CrcGlot" in actual, (
            f"java single-algo output should wrap in the default CrcGlot "
            f"container class; first 300 chars: {actual[:300]!r}"
        )
        assert f"{symbol}_init" in actual and f"{symbol}_update" in actual, (
            f"symbol={symbol!r} should become the method-name prefix "
            f"(expected '{symbol}_init' / '{symbol}_update')"
        )

    def test_list_of_one_matches_single_name(self):
        # Arrange: ["crc32"] and "crc32" should round-trip to the same
        # bytes -- single-algo path bypasses the combiner entirely.

        # Act
        actual_single = generate_catalogue("java", "crc32", "bitwise", "Crc32")
        actual_listed = generate_catalogue("java", ["crc32"], "bitwise", "Crc32")

        # Assert: byte-for-byte identical.
        assert actual_single == actual_listed, (
            "single-name and single-element-list paths should produce "
            "identical output (single-algo bypass of the combiner)"
        )

    def test_java_bundle_wraps_in_one_container_class(self):
        # Arrange: two algos bundled into one Java file -- crcglot's
        # combine_java wraps everything in a single public final class
        # named from the stem, with both algorithms' helpers inside.
        names = ["crc32", "crc16-modbus"]

        # Act
        actual = generate_catalogue("java", names, "bitwise", "MyCrcs")

        # Assert: one container class, both algorithms' init methods
        # present, classname matches the stem.
        assert isinstance(actual, str), (
            f"java bundle should be str; got {type(actual).__name__}"
        )
        assert "public final class MyCrcs" in actual, (
            "java bundle should wrap algorithms in one container class "
            "named from the stem"
        )
        assert "crc32_init" in actual and "crc16_modbus_init" in actual, (
            f"bundle should keep both algorithms' catalogue-derived "
            f"function names; got methods starting with: "
            f"{[ln.strip() for ln in actual.split(chr(10)) if 'public static' in ln][:6]!r}"
        )

    def test_c_bundle_returns_header_source_tuple(self):
        # Arrange: C generator emits (.h, .c).  Multi-algo combine_c
        # preserves that shape -- one merged header, one merged source.
        names = ["crc32", "crc16-modbus"]

        # Act
        actual = generate_catalogue("c", names, "bitwise", "mycrcs")

        # Assert: 2-tuple of non-empty strings.
        assert isinstance(actual, tuple) and len(actual) == 2, (
            f"C bundle should be a 2-tuple; got {type(actual).__name__} len "
            f"{len(actual) if isinstance(actual, tuple) else 'n/a'}"
        )
        header, source = actual
        assert header and source, (
            f"C bundle pieces should both be non-empty; got header={len(header)}, "
            f"source={len(source)}"
        )
        # The merged source should #include the bundle stem header
        # exactly once -- crcglot's combine_c rewrites the per-algo
        # self-includes to point at the merged header.
        assert source.count('#include "mycrcs.h"') == 1, (
            f"merged C source should #include the bundle stem header "
            f"exactly once; got {source.count('#include "mycrcs.h"')}"
        )
