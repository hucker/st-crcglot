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
"""
from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


# Locate streamlit_app.py relative to this test file so the suite works
# regardless of the directory pytest is invoked from.
APP = str(Path(__file__).resolve().parent.parent / "streamlit_app.py")


@pytest.fixture
def at() -> AppTest:
    """A freshly-run AppTest for each test.  30s timeout is generous --
    streamlit's first render compiles the script and warms caches."""
    return AppTest.from_file(APP, default_timeout=30).run()


# ---------- Chrome / structure ----------

def test_app_boots_without_exception(at):
    """Page-level smoke: the script runs all the way through.  Any
    uncaught Python exception would land in ``at.exception``."""
    assert not at.exception, f"app raised: {at.exception}"


def test_all_six_tabs_present(at):
    """The flat tab bar shows FAQ, Catalog Code Gen, Custom Code Gen,
    Catalog Calc, Custom Calc, Reverse Lookup."""
    assert len(at.tabs) == 6
    # Tab labels carry the emoji used in streamlit_app.py
    labels = [tab.label for tab in at.tabs]
    assert any("FAQ" in lbl for lbl in labels)
    assert any("Catalog Code Gen" in lbl for lbl in labels)
    assert any("Custom Code Gen" in lbl for lbl in labels)
    assert any("Catalog Calc" in lbl for lbl in labels)
    assert any("Custom Calc" in lbl for lbl in labels)
    assert any("Reverse Lookup" in lbl for lbl in labels)


def test_expected_subheaders_render(at):
    """Each container-bound section uses st.subheader.  Across all tabs
    these are the visible section titles we expect."""
    bodies = [s.body for s in at.subheader]
    # Pickers + actions across the four Calc/Gen tabs + Reverse Lookup
    expected_titles = {
        "Select Algorithm",
        "Select Parameters",
        "Generate code",
        "Calculate CRC",
        "Calculate/Verify CRC",
        "Reverse Lookup",
    }
    assert expected_titles <= set(bodies), (
        f"missing subheaders: {expected_titles - set(bodies)}"
    )


# ---------- FAQ tab ----------

def test_faq_leads_with_acknowledgments_section(at):
    """The FAQ markdown should start with the credits block before any
    other section.  Regression target -- 'Standing on the shoulders of
    giants' should appear before 'What CRC101 does'."""
    blocks = [m.value for m in at.markdown if m.value]
    joined = "\n".join(blocks)
    # Both headings present
    assert "Standing on the shoulders of giants" in joined
    assert "What CRC101 does" in joined
    # And the credits block comes first
    assert joined.index("Standing on the shoulders") < joined.index(
        "What CRC101 does"
    )


def test_faq_lists_all_three_acknowledgments(at):
    """Each ACKNOWLEDGMENTS entry should appear as a bullet (reveng /
    zlib / Rocksoft).  If crcglot adds or removes a credit upstream
    this test will flag it -- which is the point."""
    joined = "\n".join(m.value for m in at.markdown if m.value)
    assert "reveng CRC catalogue" in joined
    assert "zlib" in joined
    assert "Rocksoft" in joined


# ---------- Catalog Calc gold path ----------

def test_catalog_calc_test_vector_produces_check_value(at):
    """Open Catalog Calc, leave defaults (crc32 + test vector), click
    Calculate, and confirm the published check value comes back.

    The Calc tab seeds the input with b"123456789" when the test-vector
    checkbox is on at click time; the default catalog algorithm is
    crc32.  We just need to flip the checkbox and click Calculate.
    """
    # Widget keys in the source: "cat_calc_use_tv" (checkbox),
    # "cat_calc_text" (textarea), "cat_calc_go" (button).
    at.checkbox(key="cat_calc_use_tv").set_value(True).run()
    at.button(key="cat_calc_go").click().run()
    # Result block writes the formatted CRC into st.code.
    code_blocks = [c.value for c in at.code]
    assert any("0xCBF43926" in code for code in code_blocks), (
        f"expected the crc32 check value in code output; got {code_blocks!r}"
    )


# ---------- Reverse Lookup gold path ----------

def _find_button_by_label(at: AppTest, label: str):
    """Locate a button by its visible label.

    The Reverse Lookup button doesn't set ``key=``, so we can't use
    ``at.button(key=...)``.  Match on the label as the next-best stable
    identifier.
    """
    matches = [b for b in at.button if b.label == label]
    assert matches, f"no button with label {label!r}; saw {[b.label for b in at.button]}"
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
    at.segmented_control(key="rev_source").set_value("Target").run()
    at.text_area(key="rev_text").set_value("123456789").run()
    at.text_input(key="rev_target").set_value("0xCBF43926").run()
    _find_button_by_label(at, "Reverse Lookup").click().run()
    assert "crc32" in _rendered_text(at), (
        "Reverse Lookup Target mode should surface crc32 in the result"
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
    at.text_area(key="cust_calc_text").set_value("123456789").run()
    at.button(key="cust_calc_go").click().run()
    code_blocks = [c.value for c in at.code]
    assert any("0xCBF43926" in code for code in code_blocks), (
        f"Custom Calc with default crc32 params should produce 0xCBF43926; "
        f"got code blocks {code_blocks!r}"
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
    # Leave test-vector checkbox off so the textarea is honoured.
    at.text_area(key="cat_calc_text").set_value("hello world").run()
    at.button(key="cat_calc_go").click().run()
    code_blocks = [c.value for c in at.code]
    assert any("0x0D4A1185" in code for code in code_blocks), (
        f"crc32 of 'hello world' should be 0x0D4A1185; "
        f"got code blocks {code_blocks!r}"
    )


def test_catalog_code_gen_produces_non_empty_c_output(at):
    """Default Catalog Code Gen (crc32, C language, bitwise variant)
    should yield ``.h`` and ``.c`` panes whose content contains the
    user-typed symbol.  Regression target for the
    ``generate_catalogue`` wrapper: if it ever dropped ``variant=`` or
    ``symbol=`` on the way to crcglot, the output would change shape or
    miss the symbol.
    """
    # The Catalog Code Gen symbol field defaults to "crc32" for the
    # crc32 algorithm (default_symbol replaces '-' with '_').  Click
    # Generate and verify both file panes appear with code in them.
    at.button(key="cat_gen_go").click().run()
    code_blocks = [c.value for c in at.code if c.value]
    # Expect at least 2 code blocks for C (one .h, one .c).
    assert len(code_blocks) >= 2, f"expected >= 2 code panes, got {len(code_blocks)}"
    joined = "\n".join(code_blocks)
    # The symbol "crc32" must appear in the generated source (function
    # decl, table name, header guard, etc.) -- if our wrapper dropped
    # the symbol argument, crcglot would fall back to a default and
    # this assertion would fail.
    assert "crc32" in joined, (
        f"generated C code should reference the 'crc32' symbol; "
        f"joined excerpt: {joined[:300]!r}"
    )


def test_reverse_no_match_shows_warning(at):
    """When the input doesn't match any catalog algorithm under either
    byte order, the View Result block should render an ``st.warning``
    explaining common reasons.  Regression target for the no-match
    branch in ``render_reverse_tab``.
    """
    at.segmented_control(key="rev_source").set_value("Target").run()
    at.text_area(key="rev_text").set_value("not actually a packet").run()
    # A target value no algorithm produces for the above payload
    at.text_input(key="rev_target").set_value("0x12345678").run()
    _find_button_by_label(at, "Reverse Lookup").click().run()
    warnings = [w.value for w in at.warning if w.value]
    assert warnings, "expected an st.warning rendered when no match found"
    assert any("No catalog algorithm" in w for w in warnings), (
        f"warning text should explain no-match; saw {warnings!r}"
    )


def test_reverse_text_end_of_data_mode_finds_crc32(at):
    """The end-of-data text mode is a different dispatch path from the
    Target mode test above -- it exercises ``detect()``'s framing
    detection rather than the ``target_crc`` integer compare.  Both
    paths should resolve the canonical crc32 case.
    """
    # rev_source defaults to "Any", rev_input_mode defaults to "Text"
    at.text_area(key="rev_text").set_value("123456789 cbf43926").run()
    _find_button_by_label(at, "Reverse Lookup").click().run()
    assert "crc32" in _rendered_text(at), (
        "end-of-data text-mode Reverse Lookup should surface crc32"
    )


def test_hex_input_parse_error_renders_error_message(at):
    """When the Calc tab's Hex input mode receives malformed hex, the
    error path should render an ``st.error``.  Regression target for
    the input-validation wiring: a silent fallthrough to ``encode_int``
    with an empty bytes object would compute *something* but display
    the wrong CRC.
    """
    at.segmented_control(key="cat_calc_input_mode").set_value("Hex").run()
    at.text_area(key="cat_calc_text").set_value("DE AD BX EF").run()
    at.button(key="cat_calc_go").click().run()
    errors = [e.value for e in at.error if e.value]
    assert errors, "expected an st.error rendered for invalid hex input"
    # The error message comes from parse_hex_bytes
    assert any("Non-hex character" in e for e in errors), (
        f"error should mention the bad character; saw {errors!r}"
    )


def test_target_crc_field_only_renders_in_target_mode(at):
    """The ``Target CRC (hex)`` text input must only render when CRC
    source is ``Target`` -- it's hidden in the end-of-data modes (Any /
    8 / 16 / 32 / 64) where the CRC comes from the input itself.
    Regression target for the conditional ``if not end_of_data:`` block.
    """
    # Default state: rev_source = "Any" -> Target field should NOT exist
    keys_default = [t.key for t in at.text_input]
    assert "rev_target" not in keys_default, (
        f"rev_target text_input should be absent when CRC source is 'Any'; "
        f"saw keys {keys_default!r}"
    )
    # Flip to Target -> field should appear on the rerun
    at.segmented_control(key="rev_source").set_value("Target").run()
    keys_target = [t.key for t in at.text_input]
    assert "rev_target" in keys_target, (
        f"rev_target text_input should appear when CRC source is 'Target'; "
        f"saw keys {keys_target!r}"
    )
