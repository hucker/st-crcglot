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


def test_reverse_target_mode_finds_crc32(at):
    """Drive Reverse Lookup in Target mode with payload 123456789 and
    target 0xCBF43926.  Should surface crc32 as a match."""
    # Default CRC source is "Any" (Use Target sits last in the segmented
    # control); flip to Target to expose the Target CRC text input.
    at.segmented_control(key="rev_source").set_value("Target").run()
    # Drop in payload + target.  Default Input format is "Text".
    at.text_area(key="rev_text").set_value("123456789").run()
    at.text_input(key="rev_target").set_value("0xCBF43926").run()
    # Click the (now-enabled) Reverse Lookup button.
    _find_button_by_label(at, "Reverse Lookup").click().run()
    # The match algorithm name lands somewhere on the page -- as a
    # st.badge label, an st.caption description, or in the View Result
    # markdown header.  Scan everything renderable.
    rendered = "\n".join(
        [m.value for m in at.markdown if m.value]
        + [c.value for c in at.caption if c.value]
        + [getattr(b, "label", "") or "" for b in at.button]
    )
    # st.badge values aren't in markdown/caption -- they sit in the
    # rendered DOM under at.main's children.  Fall back to scanning the
    # raw element JSON if the markdown didn't catch the name.
    if "crc32" not in rendered:
        rendered = at.main.repr_for_test()
    assert "crc32" in rendered, (
        "Reverse Lookup should mention the crc32 match somewhere on the "
        f"page; truncated render: {rendered[:500]!r}"
    )
