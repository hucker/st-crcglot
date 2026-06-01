"""CRC101 -- generate and verify CRCs in the browser, powered by crcglot.

This file is intentionally slim and reads top-to-bottom as the page
structure.  Streamlit render helpers live in :mod:`ui`; all streamlit-free
logic (parsing, CRC search, stats, version helpers) lives in :mod:`crc_lib`.
"""

from __future__ import annotations

import streamlit as st

from ui import (
    inject_css,
    render_calc_tab,
    render_faq_tab,
    render_footer,
    render_gen_tab,
    render_hero,
    render_reverse_tab,
    render_seo_meta,
)


st.set_page_config(
    page_title="CRC101",
    page_icon="🛡️",
    layout="wide",
)

render_seo_meta()
inject_css()
render_hero()


tab_faq, tab_cat_gen, tab_cust_gen, tab_cat_calc, tab_cust_calc, tab_reverse = st.tabs(
    [
        "ℹ️ Show FAQ",
        "⚡ Catalog Code Gen",
        "⚡ Custom Code Gen",
        "🧮 Catalog Calc",
        "🧮 Custom Calc",
        "🔍 Reverse Lookup",
    ]
)

with tab_faq:
    render_faq_tab()

with tab_cat_gen:
    render_gen_tab(picker_kind="catalog", key_prefix="cat_gen", is_custom=False)

with tab_cust_gen:
    render_gen_tab(picker_kind="custom", key_prefix="cust_gen", is_custom=True)

with tab_cat_calc:
    render_calc_tab(picker_kind="catalog", key_prefix="cat_calc", allow_verify=True)

with tab_cust_calc:
    render_calc_tab(picker_kind="custom", key_prefix="cust_calc", allow_verify=False)

with tab_reverse:
    render_reverse_tab()


render_footer()
