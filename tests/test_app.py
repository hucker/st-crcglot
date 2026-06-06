"""Smoke tests for the streamlit app via ``streamlit.testing.v1.AppTest``.

AppTest runs ``streamlit_app.py`` headless in-process: no browser, no
network.  Each ``.run()`` does a full re-render so we keep the test
count modest and focus on whole-flow paths instead of exhaustive
widget-state checks.  The crc_lib units are covered separately in
``test_crc_lib.py``.

What we verify here:

- The app boots without exceptions (covers import-time wiring and the
  hero / FAQ / footer chrome).
- Every tab the user can click is present and titled.
- The FAQ tab leads with the ACKNOWLEDGMENTS-driven "Standing on the
  shoulders of giants" section -- a regression target since we moved
  this to the top of the page.
- The Catalog Calc gold path: pick ``crc32``, hit Calculate with the
  test vector, see the expected 0xCBF43926 in the code output.
- The Reverse Lookup gold path in Target mode: payload + target →
  crc32 match.

What we deliberately *don't* test here:

- Pill rendering / tooltip help text.  Streamlit's AppTest doesn't
  expose ``st.badge`` content in a stable way at the version we
  target, and the per-pill logic is unit-tested via ``padding_pills``
  in ``test_crc_lib.py``.
- Code generation per language.  Each language is round-tripped by
  crcglot's own test suite; re-running it here would just slow the
  smoke pass without adding signal.

Style: tests follow Arrange / Act / Assert with section-header
comments and a blank line between sections.  The ``at`` fixture
counts as the Arrange step for chrome-level checks (the freshly-run
AppTest is the arranged-state), so those tests start at Act.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


# Locate src/streamlit_app.py relative to this test file so the suite
# works regardless of the directory pytest is invoked from.
APP = str(Path(__file__).resolve().parent.parent / "src" / "streamlit_app.py")


@pytest.fixture
def at() -> AppTest:
    """A freshly-run AppTest for each test.  30s timeout is generous --
    streamlit's first render compiles the script and warms caches."""
    return AppTest.from_file(APP, default_timeout=30).run()


# ---------- Chrome / structure ----------


def test_app_boots_without_exception(at):
    """Page-level smoke: the script runs all the way through.  Any
    uncaught Python exception would land in ``at.exception``."""
    # Arrange + Act: the `at` fixture is the freshly-run AppTest.

    # Assert
    assert not at.exception, f"app raised: {at.exception}"


def test_all_six_tabs_present(at):
    """The flat tab bar shows FAQ, Catalog Code Gen, Custom Code Gen,
    Catalog Calc, Custom Calc, Reverse Lookup."""
    # Arrange + Act
    actual_count = len(at.tabs)
    expected_count = 6
    actual_labels = [tab.label for tab in at.tabs]
    expected_fragments = [
        "FAQ",
        "Catalog Code Gen",
        "Custom Code Gen",
        "Catalog Calc",
        "Custom Calc",
        "Reverse Lookup",
    ]

    # Assert: six tabs, each with the expected emoji + label fragment.
    assert actual_count == expected_count, (
        f"tab count = {actual_count}, expected {expected_count}; "
        f"labels {actual_labels!r}"
    )
    for fragment in expected_fragments:
        assert any(fragment in lbl for lbl in actual_labels), (
            f"missing tab label fragment {fragment!r}; saw {actual_labels!r}"
        )


def test_expected_subheaders_render(at):
    """Each container-bound section uses st.subheader.  Across all tabs
    these are the visible section titles we expect."""
    # Arrange: the expected set of visible section titles across all tabs.
    expected_titles = {
        "Select Algorithm",
        "Select Parameters",
        "Generate code",
        "Calculate CRC",
        "Calculate/Verify CRC",
        "Reverse Lookup",
    }

    # Act
    actual_titles = {s.body for s in at.subheader}

    # Assert: every expected title appears as a subheader somewhere.
    assert expected_titles <= actual_titles, (
        f"missing subheaders: {expected_titles - actual_titles}"
    )


# ---------- FAQ tab ----------


def test_faq_leads_with_acknowledgments_section(at):
    """The FAQ markdown should start with the credits block before any
    other section.  Regression target -- 'Standing on the shoulders of
    giants' should appear before 'What CRC101 does'."""
    # Arrange + Act: gather every markdown block on the page into one
    # searchable string.
    actual_text = "\n".join(m.value for m in at.markdown if m.value)

    # Assert: both headings present, with credits before "What CRC101 does".
    assert "Standing on the shoulders of giants" in actual_text, (
        "FAQ should contain 'Standing on the shoulders of giants' header"
    )
    assert "What CRC101 does" in actual_text, (
        "FAQ should contain 'What CRC101 does' header"
    )
    assert actual_text.index("Standing on the shoulders") < actual_text.index(
        "What CRC101 does"
    ), "credits section should appear before 'What CRC101 does'"


def test_faq_lists_all_three_acknowledgments(at):
    """Each ACKNOWLEDGMENTS entry should appear as a bullet (reveng /
    zlib / Rocksoft).  If crcglot adds or removes a credit upstream
    this test will flag it -- which is the point."""
    # Arrange + Act
    actual_text = "\n".join(m.value for m in at.markdown if m.value)
    expected_credits = ["reveng CRC catalogue", "zlib", "Rocksoft"]

    # Assert: every published ACKNOWLEDGMENTS entry appears in the FAQ.
    for credit in expected_credits:
        assert credit in actual_text, (
            f"FAQ should mention {credit!r}; not found in rendered markdown"
        )


# ---------- Catalog Calc gold path ----------


def test_catalog_calc_test_vector_produces_check_value(at):
    """Open Catalog Calc, leave defaults (crc32 + test vector), click
    Calculate, and confirm the published check value comes back.

    The Calc tab seeds the input with b"123456789" when the test-vector
    checkbox is on at click time; the default catalog algorithm is
    crc32.  We just need to flip the checkbox and click Calculate.
    """
    # Arrange: enable the test-vector checkbox so the textarea is
    # populated with b"123456789".  Widget keys in source:
    # "cat_calc_use_tv" (checkbox), "cat_calc_go" (button).
    at.checkbox(key="cat_calc_use_tv").set_value(True).run()
    expected_crc = "0xCBF43926"

    # Act: click Calculate.
    at.button(key="cat_calc_go").click().run()

    # Assert: the result block writes the formatted CRC into st.code.
    actual_codes = [c.value for c in at.code]
    assert any(expected_crc in code for code in actual_codes), (
        f"expected {expected_crc} in code output; got {actual_codes!r}"
    )


# ---------- Reverse Lookup gold path ----------


def _find_button_by_label(at: AppTest, label: str):
    """Locate a button by its visible label.

    The Reverse Lookup button doesn't set ``key=``, so we can't use
    ``at.button(key=...)``.  Match on the label as the next-best stable
    identifier.
    """
    matches = [b for b in at.button if b.label == label]
    assert matches, (
        f"no button with label {label!r}; saw {[b.label for b in at.button]}"
    )
    return matches[0]


def _rendered_text(at: AppTest) -> str:
    """Concatenate everything renderable into one searchable string.

    Used as a coarse "did the algorithm name / desc / warning text
    end up on the page" check.  ``st.badge`` content isn't in the
    AppTest accessors so the pill labels themselves aren't searchable
    here -- but the algorithm desc (a ``st.caption``) is, which is
    enough to confirm the result row was rendered.
    """
    return "\n".join(
        [m.value for m in at.markdown if m.value]
        + [c.value for c in at.caption if c.value]
        + [w.value for w in at.warning if w.value]
    )


def test_reverse_target_mode_finds_crc32(at):
    """Drive Reverse Lookup in Target mode with payload 123456789 and
    target 0xCBF43926.  Should surface crc32 as a match."""
    # Arrange: flip to Target mode, populate payload + target.
    at.segmented_control(key="rev_source").set_value("Target").run()
    at.text_area(key="rev_text").set_value("123456789").run()
    at.text_input(key="rev_target").set_value("0xCBF43926").run()
    expected_alg = "crc32"

    # Act: click the (now-enabled) Reverse Lookup button.
    _find_button_by_label(at, "Reverse Lookup").click().run()

    # Assert: crc32 appears somewhere in the rendered text.
    actual_text = _rendered_text(at)
    assert expected_alg in actual_text, (
        f"Target-mode Reverse Lookup should surface {expected_alg!r}; "
        f"rendered text excerpt: {actual_text[:300]!r}"
    )


# ---------- Deeper coverage ----------


def test_custom_calc_with_default_crc32_params_matches_check(at):
    """End-to-end test of the Custom Calc dispatch:

    - ``render_custom_picker`` builds an ``AlgorithmInfo`` from the form
      fields,
    - ``render_calculate_section`` routes it to ``generic_crc`` (custom
      path, not ``encode_int``),
    - the result panel renders the computed value as hex.

    Custom Calc has no "Use test vector" checkbox (allow_verify=False),
    so we manually feed ``"123456789"`` into the textarea.  The default
    custom-form values are the crc32 parameters, so the result must
    equal ``0xCBF43926``.  If the dispatch wrongly routed to the
    catalog path -- which calls ``encode_int("custom", ...)`` and would
    raise ValueError because "custom" isn't a registered name -- this
    test would fail with an exception, not an assertion mismatch.
    """
    # Arrange: feed "123456789" into Custom Calc's textarea (custom
    # params default to crc32, so this should match the catalog check).
    at.text_area(key="cust_calc_text").set_value("123456789").run()
    expected_crc = "0xCBF43926"

    # Act: click Calculate.
    at.button(key="cust_calc_go").click().run()

    # Assert
    actual_codes = [c.value for c in at.code]
    assert any(expected_crc in code for code in actual_codes), (
        f"Custom Calc with default crc32 params should produce {expected_crc}; "
        f"got code blocks {actual_codes!r}"
    )


def test_catalog_calc_with_raw_text_input(at):
    """End-to-end with a *non*-test-vector input.  Verifies the input
    text actually gets fed into ``encode_int`` rather than the calc
    silently using the catalog's pre-published check value (which would
    pass the test_vector test by accident regardless).

    Uses ``"hello world"`` whose crc32 is ``0x0D4A1185`` -- not equal to
    crc32's catalog check value, so a regression that returns
    ``entry.check`` instead of computing from input would be caught.
    """
    # Arrange: leave the test-vector checkbox off so the textarea is
    # honored, then feed "hello world" into it.
    at.text_area(key="cat_calc_text").set_value("hello world").run()
    expected_crc = "0x0D4A1185"  # crc32 of "hello world", not the catalog check

    # Act
    at.button(key="cat_calc_go").click().run()

    # Assert: the input was actually fed into encode_int (not silently
    # replaced with the catalog check value).
    actual_codes = [c.value for c in at.code]
    assert any(expected_crc in code for code in actual_codes), (
        f"crc32 of 'hello world' should be {expected_crc}; "
        f"got code blocks {actual_codes!r}"
    )


def test_catalog_code_gen_produces_non_empty_c_output(at):
    """Default Catalog Code Gen (crc32, C language, bitwise variant)
    should yield ``.h`` and ``.c`` panes whose content contains the
    user-typed symbol.  Regression target for the
    ``generate_catalogue`` wrapper: if it ever dropped ``variant=`` or
    ``symbol=`` on the way to crcglot, the output would change shape or
    miss the symbol.
    """
    # Arrange: no widget setup needed -- the Catalog Code Gen defaults
    # are crc32 + C + bitwise + symbol="crc32" (default_symbol replaces
    # '-' with '_').
    expected_min_panes = 2  # one .h, one .c
    expected_symbol = "crc32"

    # Act
    at.button(key="cat_gen_go").click().run()

    # Assert: both file panes appear with code referencing the symbol.
    actual_codes = [c.value for c in at.code if c.value]
    assert len(actual_codes) >= expected_min_panes, (
        f"expected >= {expected_min_panes} code panes; got {len(actual_codes)}"
    )
    actual_joined = "\n".join(actual_codes)
    # If our wrapper dropped the symbol argument, crcglot would fall
    # back to a default and this assertion would fail.
    assert expected_symbol in actual_joined, (
        f"generated C code should reference the {expected_symbol!r} symbol; "
        f"joined excerpt: {actual_joined[:300]!r}"
    )


def test_catalog_code_gen_bundles_multiple_algorithms_into_one_java_file(at):
    """Catalog Code Gen with multi-select + Java target should route
    through crcglot's ``combine_java`` and emit a single ``.java`` file
    that contains *both* algorithms' helpers inside one container class.

    Regression target for the multi-algorithm path added in crcglot
    0.12: if the wrapper accidentally fell back to single-algo
    generation, only the first selected algorithm's functions would
    appear in the output and `crc16_modbus_init` would be missing.
    """
    # Arrange: switch the catalog gen picker to a 2-algo bundle, pick
    # Java, type a container/file stem, and click Generate.
    at.multiselect(key="cat_gen_alg_multiselect").set_value(
        ["crc32", "crc16-modbus"]
    ).run()
    at.segmented_control(key="cat_gen_lang").set_value("java").run()
    at.text_input(key="cat_gen_symbol").set_value("MyCrcs").run()
    expected_class = "public final class MyCrcs"
    expected_methods = ("crc32_init", "crc16_modbus_init")

    # Act
    at.button(key="cat_gen_go").click().run()

    # Assert: exactly one Java pane (single-file language) wrapping both
    # algorithms' init helpers under the stem-named container class.
    actual_codes = [c.value for c in at.code if c.value]
    actual_joined = "\n".join(actual_codes)
    assert expected_class in actual_joined, (
        f"java bundle should wrap both algorithms in a class named from "
        f"the file stem; first 400 chars: {actual_joined[:400]!r}"
    )
    for method in expected_methods:
        assert method in actual_joined, (
            f"java bundle should contain {method!r} (one per bundled "
            f"algorithm); methods found: "
            f"{[ln.strip() for ln in actual_joined.split(chr(10)) if 'public static' in ln][:8]!r}"
        )


def test_catalog_code_gen_passes_comment_style_to_java_doxygen(at):
    """Catalog Code Gen with Java + Doxygen should produce output
    carrying Doxygen block markers (`/**`, `@param`).

    Regression target for the new Comment style picker added in this
    PR: if the picker's value were dropped on the way through
    ``render_generate_section`` → ``generate_catalogue`` → crcglot,
    the output would silently emit `plain` and the `@param` assert
    would fail.  Picks Java (single-file language) so the assertion
    is against one combined pane rather than .h/.c side-by-side.
    """
    # Arrange: keep default crc32 selection; switch language to Java
    # and comment style to Doxygen.
    at.segmented_control(key="cat_gen_lang").set_value("java").run()
    at.segmented_control(key="cat_gen_comment_style").set_value("doxygen").run()
    expected_block_marker = "/**"
    expected_tag = "@param"

    # Act
    at.button(key="cat_gen_go").click().run()

    # Assert: Doxygen block-comment markers present.  Plain Java would
    # carry `//` line comments and no `@param` tags; Doxygen renders
    # `/** @brief @param @return */` block comments.
    actual_codes = [c.value for c in at.code if c.value]
    actual_joined = "\n".join(actual_codes)
    assert expected_block_marker in actual_joined, (
        f"java + doxygen output should carry Doxygen block-comment "
        f"opener {expected_block_marker!r}; first 400 chars: "
        f"{actual_joined[:400]!r}"
    )
    assert expected_tag in actual_joined, (
        f"java + doxygen output should carry the {expected_tag!r} tag "
        f"on at least one function; first 400 chars: "
        f"{actual_joined[:400]!r}"
    )


def test_reverse_no_match_shows_warning(at):
    """When the input doesn't match any catalog algorithm under either
    byte order, the View Result block should render an ``st.warning``
    explaining common reasons.  Regression target for the no-match
    branch in ``render_reverse_tab``.
    """
    # Arrange: Target mode with payload + target that no catalog
    # algorithm produces.
    at.segmented_control(key="rev_source").set_value("Target").run()
    at.text_area(key="rev_text").set_value("not actually a packet").run()
    at.text_input(key="rev_target").set_value("0x12345678").run()
    expected_warning_fragment = "No catalog algorithm"

    # Act
    _find_button_by_label(at, "Reverse Lookup").click().run()

    # Assert: an st.warning with the no-match explanation appears.
    actual_warnings = [w.value for w in at.warning if w.value]
    assert actual_warnings, (
        "expected an st.warning rendered when no algorithm matched the input"
    )
    assert any(expected_warning_fragment in w for w in actual_warnings), (
        f"warning text should contain {expected_warning_fragment!r}; "
        f"got {actual_warnings!r}"
    )


def test_reverse_text_end_of_data_mode_finds_crc32(at):
    """The end-of-data text mode is a different dispatch path from the
    Target mode test above -- it exercises ``detect()``'s framing
    detection rather than the ``target_crc`` integer compare.  Both
    paths should resolve the canonical crc32 case.
    """
    # Arrange: defaults are rev_source="Any" and rev_input_mode="Text",
    # so just populate the input area with payload + trailing hex CRC.
    at.text_area(key="rev_text").set_value("123456789 cbf43926").run()
    expected_alg = "crc32"

    # Act
    _find_button_by_label(at, "Reverse Lookup").click().run()

    # Assert: text-mode end-of-data should surface the crc32 match.
    actual_text = _rendered_text(at)
    assert expected_alg in actual_text, (
        f"end-of-data text-mode Reverse Lookup should surface "
        f"{expected_alg!r}; rendered excerpt: {actual_text[:300]!r}"
    )


def test_hex_input_parse_error_renders_error_message(at):
    """When the Calc tab's Hex input mode receives malformed hex, the
    error path should render an ``st.error``.  Regression target for
    the input-validation wiring: a silent fallthrough to ``encode_int``
    with an empty bytes object would compute *something* but display
    the wrong CRC.
    """
    # Arrange: switch Catalog Calc to Hex input mode, paste a string
    # with one non-hex character.
    at.segmented_control(key="cat_calc_input_mode").set_value("Hex").run()
    at.text_area(key="cat_calc_text").set_value("DE AD BX EF").run()
    expected_error_fragment = "Non-hex character"

    # Act
    at.button(key="cat_calc_go").click().run()

    # Assert: the parser error from parse_hex_bytes surfaces via st.error.
    actual_errors = [e.value for e in at.error if e.value]
    assert actual_errors, "expected an st.error rendered for invalid hex input"
    assert any(expected_error_fragment in e for e in actual_errors), (
        f"error should contain {expected_error_fragment!r}; saw {actual_errors!r}"
    )


def test_target_crc_field_only_renders_in_target_mode(at):
    """The ``Target CRC (hex)`` text input must only render when CRC
    source is ``Target`` -- it's hidden in the end-of-data modes (Any /
    8 / 16 / 32 / 64) where the CRC comes from the input itself.
    Regression target for the conditional ``if not end_of_data:`` block.
    """
    # Arrange + Act: default state has rev_source = "Any", so the
    # Target CRC field should NOT exist yet.
    actual_default_keys = [t.key for t in at.text_input]

    # Assert (first half): rev_target absent in "Any" mode.
    assert "rev_target" not in actual_default_keys, (
        f"rev_target should be absent when CRC source is 'Any'; "
        f"saw keys {actual_default_keys!r}"
    )

    # Act: flip to Target mode and re-run.
    at.segmented_control(key="rev_source").set_value("Target").run()
    actual_target_keys = [t.key for t in at.text_input]

    # Assert (second half): rev_target appears in Target mode.
    assert "rev_target" in actual_target_keys, (
        f"rev_target should appear when CRC source is 'Target'; "
        f"saw keys {actual_target_keys!r}"
    )
