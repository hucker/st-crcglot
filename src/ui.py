"""Streamlit render helpers for CRC101.

Every streamlit-touching function lives here -- page chrome (CSS, SEO, hero,
footer), the algorithm pickers, the generate/calculate/test-vector sections,
and the three tab-body composers (render_calc_tab / render_gen_tab /
render_reverse_tab).  Pure-Python logic lives in :mod:`crc_lib`.

``streamlit_app.py`` is intentionally slim and only imports the public render
functions (chrome + tab bodies); the shared pickers/sections are internal
implementation details of the tab bodies.
"""

from __future__ import annotations

import streamlit as st

from crc_lib import (
    ACKNOWLEDGMENTS,
    ALGORITHMS,
    AlgorithmInfo,
    CALC_KEY,
    LANGUAGES,
    NAMING_ORDER,
    RECOVER_KEY,
    REPO_URL,
    REVERSE_KEY,
    SENTINEL_CUSTOM,
    alg_label,
    app_version,
    CrcStream,
    available_variants_bundle,
    bump_stats,
    catalogue_names,
    crc_stream,
    crcglot_version,
    default_stem,
    detect_chunk,
    encode_int,
    generate_source_files,
    generic_crc,
    git_revision,
    lang_label,
    load_stats,
    naming_info,
    padding_pills,
    parse_hex,
    parse_hex_bytes,
    recover_packets,
    style_info,
    style_label,
    variant_info,
    variant_label,
)


# ---------- Page chrome ----------


def render_seo_meta() -> None:
    """Emit the SEO meta block into the page.

    The tags land in ``<body>``, not ``<head>``, because Streamlit doesn't
    expose a way to write into ``<head>``.  Modern Google (which JS-renders)
    picks them up; strict / non-JS crawlers won't.  A reverse-proxy
    rewriting the served HTML would be the real fix.
    """
    n = len(ALGORITHMS)
    # Language list reads live from crcglot so new targets (Java in 0.12,
    # whatever ships in 0.13) appear in the meta tags without an SEO edit.
    lang_names = [LANGUAGES[k].display_name for k in LANGUAGES]
    if len(lang_names) > 1:
        langs_csv = ", ".join(lang_names[:-1]) + ", and " + lang_names[-1]
        langs_or = ", ".join(lang_names[:-1]) + ", or " + lang_names[-1]
    else:
        langs_csv = langs_or = lang_names[0]
    keywords_langs = ", ".join(lang_names)
    nlangs = len(lang_names)
    st.markdown(
        f"""
<meta name="description" content="CRC101 -- generate and verify CRCs in your browser. Catalog of {n} algorithms, code emitters for {langs_csv} ({nlangs} languages), plus an interactive calculator.">
<meta name="keywords" content="CRC, CRC-8, CRC-16, CRC-32, CRC-64, CRC calculator, CRC code generator, cyclic redundancy check, reveng catalogue, polynomial, crcglot, {keywords_langs}">
<meta name="author" content="Chuck Bass / acrocad.net">
<meta name="robots" content="index, follow">

<meta property="og:title" content="CRC101 -- CRC code generator & calculator">
<meta property="og:description" content="Generate CRC code in {langs_or} from {n} catalog algorithms -- or calculate a CRC over your own bytes.">
<meta property="og:type" content="website">

<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="CRC101 -- CRC code generator & calculator">
<meta name="twitter:description" content="Generate CRC code in {langs_or} from {n} catalog algorithms -- or calculate a CRC over your own bytes.">
        """,
        unsafe_allow_html=True,
    )


def inject_css() -> None:
    """Inject the page-wide style sheet.

    Defines visual styling for metric tiles, the custom-algorithm 4x2 grid,
    section pills, match badges (green / red / amber), the hero strip with
    its orange ``101`` accent, the footer counter row, and the build line.
    Call once near the top of the page.
    """
    st.markdown(
        """
<style>
    .block-container { padding-top: 1rem; }

    [data-testid="stCodeBlock"] {
        border-radius: 10px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
        overflow: hidden;
    }

    [data-testid="stMetric"] {
        background: #FAFAFA;
        border: 1px solid #E5E7EB;
        border-radius: 10px;
        padding: 0.75rem 1rem;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
        transition: border-color 0.15s ease-in-out;
    }
    [data-testid="stMetric"]:hover { border-color: #FF6B35; }
    [data-testid="stMetricValue"] {
        font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', monospace;
        font-size: 1.15rem;
        color: #FF6B35;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.78rem;
        opacity: 0.75;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-weight: 600;
    }

    [data-testid="stTextInput"] input[aria-label$="(hex)"] {
        font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', monospace;
        font-size: 0.95rem;
        letter-spacing: 0.02em;
    }

    /* Match any st.container(key="...custom-grid") regardless of tab prefix. */
    [class*="custom-grid"] [data-testid="stColumn"] {
        background: #FAFAFA;
        border: 1px solid #E5E7EB;
        border-radius: 10px;
        padding: 0.6rem 0.85rem;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
    }
    [class*="custom-grid"] [data-testid="stColumn"]:has(.crc-grid-empty) {
        background: transparent;
        border: none;
        box-shadow: none;
        padding: 0;
    }

    .crc-hero h1 {
        margin: 0 0 0.15rem 0;
        font-weight: 700;
        letter-spacing: -0.015em;
        font-size: 2.8rem;
    }
    .crc-hero h1 .crc-hero-101 { color: #FF6B35; }
    .crc-hero .crc-subtitle {
        margin: 0;
        font-size: 0.95rem;
        opacity: 0.65;
    }
    .crc-hero .crc-subtitle a {
        color: #FF6B35;
        text-decoration: none;
        font-weight: 600;
    }
    .crc-hero .crc-subtitle a:hover { text-decoration: underline; }
    .crc-hero { padding-bottom: 0.6rem; }

    .crc-build {
        margin-top: 0.5rem;
        font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', monospace;
        font-size: 0.72rem;
        opacity: 0.45;
        letter-spacing: 0.02em;
    }
    .crc-build a {
        color: inherit;
        text-decoration: none;
        border-bottom: 1px dotted currentColor;
    }
    .crc-build a:hover { color: #FF6B35; }
</style>
        """,
        unsafe_allow_html=True,
    )


def render_hero() -> None:
    """Render the branded hero strip at the top of the page.

    Includes the ``🛡️ CRC101`` headline (with ``101`` in orange) and the
    subtitle that links to reveng, crcglot's GitHub repo, and crcglot on
    PyPI.
    """
    st.markdown(
        """
<div class="crc-hero">
  <h1>🛡️ CRC<span class="crc-hero-101">101</span></h1>
  <p class="crc-subtitle">
    Generate CRC code &middot; calculate CRCs &middot; catalog from
    <a href="https://reveng.sourceforge.io/crc-catalogue/all.htm" target="_blank">reveng</a>
    &middot; powered by
    <a href="https://github.com/hucker/crcglot" target="_blank">crcglot</a>
    &middot; <a href="https://pypi.org/project/crcglot/" target="_blank">PyPI</a>
    &middot; <a href="https://github.com/hucker/st-crcglot#readme" target="_blank">docs</a>
  </p>
</div>
        """,
        unsafe_allow_html=True,
    )


# ---------- Picker render helpers (shared by tab bodies) ----------


def render_standard_picker(key_prefix: str) -> tuple[str, AlgorithmInfo, int]:
    """Render the catalog selectbox plus a collapsed All-parameters expander.

    Always returns a valid algorithm; ``crc32`` is the first-call default.
    The user's last selection is remembered in session-state under
    ``f"{key_prefix}_last_catalogue"`` so the picker stays put across reruns.

    Args:
        key_prefix: Per-tab namespace for streamlit widget keys.  Use a
            distinct value per tab so two pickers on different tabs don't
            collide in session-state (e.g. ``"cat_calc"`` and ``"cat_gen"``).

    Returns:
        A ``(name, entry, width)`` tuple:
            - ``name``: catalog algorithm name (e.g. ``"crc32"``).
            - ``entry``: the full :class:`AlgorithmInfo` for that algorithm.
            - ``width``: ``entry.width`` (echoed for caller convenience).
    """
    state_key = f"{key_prefix}_last_catalogue"
    if state_key not in st.session_state:
        st.session_state[state_key] = "crc32"

    name = st.selectbox(
        f"CRC algorithm ({len(catalogue_names)} available)",
        catalogue_names,
        format_func=alg_label,
        index=catalogue_names.index(st.session_state[state_key]),
        key=f"{key_prefix}_alg_select",
        help=(
            f"{len(catalogue_names)} named algorithms from Greg Cook's "
            "[reveng catalogue](https://reveng.sourceforge.io/crc-catalogue/all.htm)."
        ),
    )
    st.session_state[state_key] = name
    entry = ALGORITHMS[name]

    # Vertically-efficient parameter dump: 4-column markdown table laying
    # out 6 short fields as 3 label/value pairs per row, with description
    # below as a caption.  Replaces the previous st.expander + st.json --
    # always visible (it's small), uses native markdown rendering.
    st.markdown(
        "|  |  |  |  |\n"
        "|---|---|---|---|\n"
        f"| **Width** | {entry.width} bits | **Polynomial** | `0x{entry.poly:X}` |\n"
        f"| **Init** | `0x{entry.init:X}` | **Check** | `0x{entry.check:X}` |\n"
        f"| **Xorout** | `0x{entry.xorout:X}` | **Reflect** | "
        f"in=`{entry.refin}`, out=`{entry.refout}` |\n"
        f"| **Source** | `{entry.source}` |  |  |\n"
    )
    if entry.desc:
        st.caption(f"_{entry.desc}_")

    return name, entry, entry.width


def _is_overridden(current: str | None, auto: str | None) -> bool:
    """True when an auto-seeded field now holds a hand-typed value.

    A reseed-eligible field (the basename, the custom algorithm name)
    counts as overridden once it holds a non-empty value that differs
    from the last value *we* seeded into it -- at which point selection
    or width changes leave it alone.  An empty field is never an
    override, so clearing it re-enables auto-seeding.
    """
    return bool((current or "").strip()) and current != auto


def _auto_check_value(key_prefix: str, seed: AlgorithmInfo) -> str | None:
    """Compute the test-vector check from the custom form's live params.

    The check value (CRC of ``b"123456789"``) is fully determined by the
    other parameters, so when Auto-calculate is on we derive it here and
    show it read-only instead of making the user supply it.  Reads the
    current widget values from session state (falling back to ``seed`` on
    first render, before the widgets exist).  Returns the ``0x``-hex
    string, or ``None`` if any hex field doesn't parse -- in which case
    that field's own validation error surfaces instead.
    """
    w = int(st.session_state.get(f"{key_prefix}_width", seed.width))
    refin = st.session_state.get(f"{key_prefix}_refin", seed.refin)
    refout = st.session_state.get(f"{key_prefix}_refout", seed.refout)
    poly, pe = parse_hex(
        st.session_state.get(f"{key_prefix}_poly", f"0x{seed.poly:X}"), "Polynomial", w
    )
    init, ie = parse_hex(
        st.session_state.get(f"{key_prefix}_init", f"0x{seed.init:X}"), "Init", w
    )
    xorout, xe = parse_hex(
        st.session_state.get(f"{key_prefix}_xorout", f"0x{seed.xorout:X}"), "Xorout", w
    )
    if pe or ie or xe or poly is None or init is None or xorout is None:
        return None
    crc = generic_crc(b"123456789", w, poly, init, refin, refout, xorout)
    return f"0x{crc:0{(w + 3) // 4}X}"


def render_multi_standard_picker(
    key_prefix: str,
) -> tuple[list[str], AlgorithmInfo | None, list[int]]:
    """Multi-select sibling of :func:`render_standard_picker`.

    Used by Catalog Code Gen so the user can bundle several algorithms
    into one generated file (crcglot 0.12+ feature -- the language's
    ``combiner`` merges per-algorithm outputs without symbol collisions).
    Calc tabs keep the single-select picker because you only calculate
    one CRC at a time.

    Returns ``(names, first_entry, widths)``:
        - ``names``: algorithms in catalogue order (width then name).
            Empty list when the user has cleared the multiselect; the
            caller is responsible for disabling Generate in that case.
        - ``first_entry``: :class:`AlgorithmInfo` of the first selected
            algorithm, used by the test-vector pill (only shown when
            exactly one is selected) and the parameter table (shown only
            for single-algo to avoid wall-of-tables).  ``None`` when
            the selection is empty.
        - ``widths``: per-selected-algorithm widths, used by the variant
            picker to filter to variants every algorithm supports.
    """
    state_key = f"{key_prefix}_last_catalogue_multi"
    if state_key not in st.session_state:
        st.session_state[state_key] = ["crc32"]

    def _reseed_basename_on_alg_change() -> None:
        """Re-default the Code Gen basename when the selection changes.

        The default is whatever ``crcglot.default_stem`` derives from the
        selection -- one algorithm's name for a single pick, a combined
        stem for a bundle (crcglot owns both, so the app holds no naming
        rule of its own).  This is the language-independent *stem*; the
        per-language casing is applied for display by the preview, not
        baked into the field.  A basename the user typed by hand is
        preserved -- we only overwrite a value we ourselves last
        auto-seeded (tracked in ``*_symbol_auto``).

        This lives on the multiselect's ``on_change`` rather than inline
        in :func:`render_generate_section` because a callback can set the
        text_input's session-state value as a genuine change
        notification; an inline set-before-instantiate races the
        widget's own retained value and can leave the stale bundle stem
        on screen after dropping back to one algorithm.
        """
        raw_sel = st.session_state.get(f"{key_prefix}_alg_multiselect", [])
        sel = [n for n in catalogue_names if n in set(raw_sel)]
        if not sel:
            return
        new_default = default_stem(sel)
        sym_key = f"{key_prefix}_symbol"
        sym_auto_key = f"{key_prefix}_symbol_auto"
        if not _is_overridden(
            st.session_state.get(sym_key), st.session_state.get(sym_auto_key)
        ):
            st.session_state[sym_key] = new_default
            st.session_state[sym_auto_key] = new_default

    raw = st.multiselect(
        f"CRC algorithm(s) ({len(catalogue_names)} available)",
        catalogue_names,
        default=[n for n in st.session_state[state_key] if n in catalogue_names]
        or ["crc32"],
        format_func=alg_label,
        key=f"{key_prefix}_alg_multiselect",
        on_change=_reseed_basename_on_alg_change,
        help=(
            f"{len(catalogue_names)} named algorithms from Greg Cook's "
            "[reveng catalogue](https://reveng.sourceforge.io/crc-catalogue/all.htm).  "
            "Pick one for a single source file, or several to have crcglot "
            "bundle them into one combined output (each algorithm keeps its "
            "catalogue-derived function names)."
        ),
    )
    # Keep selection in catalogue order so generated bundles are stable
    # under reorderings the multiselect might introduce.
    names = [n for n in catalogue_names if n in set(raw)]
    st.session_state[state_key] = names

    if not names:
        st.warning(
            "Select at least one algorithm to generate code.",
            icon=":material/warning:",
        )
        return [], None, []

    first_entry = ALGORITHMS[names[0]]
    widths = [ALGORITHMS[n].width for n in names]

    # Single-algo: show the same parameter table the selectbox picker
    # uses, since one algorithm fits cleanly.  Multi-algo: collapse to
    # one summary row -- a wall of tables would dominate the viewport.
    if len(names) == 1:
        e = first_entry
        st.markdown(
            "|  |  |  |  |\n"
            "|---|---|---|---|\n"
            f"| **Width** | {e.width} bits | **Polynomial** | `0x{e.poly:X}` |\n"
            f"| **Init** | `0x{e.init:X}` | **Check** | `0x{e.check:X}` |\n"
            f"| **Xorout** | `0x{e.xorout:X}` | **Reflect** | "
            f"in=`{e.refin}`, out=`{e.refout}` |\n"
            f"| **Source** | `{e.source}` |  |  |\n"
        )
        if e.desc:
            st.caption(f"_{e.desc}_")
    else:
        width_summary = ", ".join(f"{w}-bit" for w in widths)
        st.caption(
            f"Bundling **{len(names)}** algorithms ({width_summary}) into "
            "one generated file.  Each algorithm keeps its catalogue-derived "
            "function names; the **File basename** below becomes the file "
            "stem (and, for Java, the container class name)."
        )

    return names, first_entry, widths


def render_custom_picker(
    key_prefix: str,
) -> tuple[AlgorithmInfo | None, int, str | None]:
    """Render the 4x2 custom-parameter form.

    Form layout:
        - Row 1: Refin checkbox | Width number-input | Polynomial hex |
            Init hex.
        - Row 2: Refout checkbox | Check hex | Xorout hex | (empty cell).
        - Below: a "CRC Algorithm Name" text-input (default
            ``crc<width>_custom``) that becomes the
            :class:`AlgorithmInfo`'s ``desc`` and seeds the basename in
            :func:`render_generate_section`.

    The form seeds itself from whatever catalog algorithm the user last
    picked on the matching Catalog-side tab (remembered under
    ``f"{key_prefix}_last_catalogue"``), defaulting to ``crc32``.  All hex
    fields are validated via :func:`crc_lib.parse_hex` against the
    declared width; the first failing field surfaces as a red error and
    suppresses construction of the :class:`AlgorithmInfo`.

    Args:
        key_prefix: Per-tab namespace for streamlit widget keys.

    Returns:
        A ``(entry, width, custom_error)`` tuple:
            - ``entry``: a freshly-constructed :class:`AlgorithmInfo`, or
              ``None`` when any field failed validation.
            - ``width``: the user's typed width, regardless of validation
              status (so callers can show it in messages).
            - ``custom_error``: the first validation error message, or
              ``None`` when everything parsed cleanly.
    """
    state_key = f"{key_prefix}_last_catalogue"
    if state_key not in st.session_state:
        st.session_state[state_key] = "crc32"

    def _follow_basename(name: str) -> None:
        """Seed the basename from the custom algorithm name, unless typed over.

        The same name-drives-basename relationship the catalogue side has
        (where the picked algorithm seeds the stem), so Custom Code Gen
        mirrors that UI rather than carrying its own static default.
        """
        sym_key, sym_auto = f"{key_prefix}_symbol", f"{key_prefix}_symbol_auto"
        if not _is_overridden(
            st.session_state.get(sym_key), st.session_state.get(sym_auto)
        ):
            base = default_stem(name or "crc_custom")
            st.session_state[sym_key] = base
            st.session_state[sym_auto] = base

    def _on_width_change() -> None:
        """Track the bit-width in the default name (``crc<width>_custom``).

        Matches the catalogue naming style (`crc16`, `crc32`, …) and
        cascades to the basename, both preserved once hand-edited.
        """
        w = int(st.session_state.get(f"{key_prefix}_width", 32))
        name = f"crc{w}_custom"
        name_key, name_auto = f"{key_prefix}_desc", f"{key_prefix}_desc_auto"
        if not _is_overridden(
            st.session_state.get(name_key), st.session_state.get(name_auto)
        ):
            st.session_state[name_key] = name
            st.session_state[name_auto] = name
        _follow_basename(st.session_state.get(name_key) or name)

    def _on_name_change() -> None:
        """User edited the algorithm name -> re-seed the basename to match."""
        _follow_basename(st.session_state.get(f"{key_prefix}_desc") or "crc_custom")

    seed = ALGORITHMS[st.session_state[state_key]]
    st.caption(
        f"Custom parameters — seeded from "
        f"`{st.session_state[state_key]}`. "
        "All hex fields accept `0x...` or bare hex (e.g. `1021`)."
    )

    # Auto-calculate the check value (default on).  Since the test-vector
    # CRC is fully determined by the other parameters, by default we
    # compute it live and render Check read-only -- the user never has to
    # know or type it.  Seed the field's session-state *before* the grid
    # renders (the value depends on Xorout, which renders after Check), so
    # the disabled field shows the current value with no one-rerun lag.
    check_key = f"{key_prefix}_check"
    auto_check_key = f"{key_prefix}_auto_check"
    st.session_state.setdefault(check_key, f"0x{seed.check:X}")
    st.session_state.setdefault(auto_check_key, True)
    auto_check = st.session_state[auto_check_key]
    if auto_check:
        computed = _auto_check_value(key_prefix, seed)
        if computed is not None:
            st.session_state[check_key] = computed

    # 4-column x 2-row grid so every cell has the same width.
    # Row 1: Refin   | Width | Polynomial | Init
    # Row 2: Refout  | Check | Xorout     | (empty)
    with st.container(key=f"{key_prefix}_custom-grid"):
        r1c1, r1c2, r1c3, r1c4 = st.columns(4, vertical_alignment="bottom")
        with r1c1:
            refin = st.checkbox(
                "Reflect input (refin)",
                value=seed.refin,
                key=f"{key_prefix}_refin",
            )
        with r1c2:
            width = st.number_input(
                "Width (bits)",
                min_value=1,
                max_value=64,
                value=int(seed.width),
                step=1,
                key=f"{key_prefix}_width",
                on_change=_on_width_change,
                help="CRC register width, 1-64 bits.",
            )
        with r1c3:
            poly_raw = st.text_input(
                "Polynomial (hex)",
                value=f"0x{seed.poly:X}",
                key=f"{key_prefix}_poly",
                help=(
                    "**Generator polynomial** as a `width`-bit value with "
                    "the implicit leading bit dropped.\n\n"
                    "Example: CRC-32 uses `0x04C11DB7` — the polynomial "
                    "x³² + x²⁶ + x²³ + … + 1, truncated to 32 bits."
                ),
            )
        with r1c4:
            init_raw = st.text_input(
                "Init (hex)",
                value=f"0x{seed.init:X}",
                key=f"{key_prefix}_init",
                help=(
                    "**Initial register value** loaded before any input "
                    "bytes are processed.\n\n"
                    "Typical values:\n"
                    "- `0xFFFFFFFF` — CRC-32\n"
                    "- `0xFFFF` — CRC-16/MODBUS\n"
                    "- `0x0000` — CRC-16/ARC"
                ),
            )

        r2c1, r2c2, r2c3, r2c4 = st.columns(4, vertical_alignment="bottom")
        with r2c1:
            refout = st.checkbox(
                "Reflect output (refout)",
                value=seed.refout,
                key=f"{key_prefix}_refout",
            )
        with r2c2:
            check_raw = st.text_input(
                "Check (hex)",
                key=check_key,
                disabled=auto_check,
                help=(
                    "**Test-vector check value** — the CRC of the ASCII "
                    'bytes `"123456789"`, baked into the generated '
                    "`*_self_test()`.\n\n"
                    "Auto-calculated from the parameters by default "
                    "(read-only).  Untick **Auto-calculate** to type a "
                    "known value instead; the computed-vs-typed comparison "
                    "below then flags a mismatch."
                ),
            )
        with r2c3:
            xorout_raw = st.text_input(
                "Xorout (hex)",
                value=f"0x{seed.xorout:X}",
                key=f"{key_prefix}_xorout",
                help=(
                    "**Final XOR mask** applied to the register after all "
                    "input bytes have been processed (and after output "
                    "reflection, if any).\n\n"
                    "Typical values:\n"
                    "- `0xFFFFFFFF` — CRC-32\n"
                    "- `0x0000` — CRC-16/ARC, CRC-16/MODBUS"
                ),
            )
        with r2c4:
            st.checkbox(
                "Auto-calculate check value",
                key=auto_check_key,
                help=(
                    "**On**: compute **Check** live from the parameters and "
                    "lock the field — the generated self-test then passes by "
                    "construction.\n\n"
                    "**Off**: type a known check value to assert your "
                    "parameters are correct (a mismatch is flagged below)."
                ),
            )

    # Seed via session state (not `value=`) so the width/name callbacks can
    # rewrite the field without Streamlit's default-vs-state conflict; the
    # *_auto anchor lets the override check tell an auto value from a typed
    # one.
    st.session_state.setdefault(f"{key_prefix}_desc", f"crc{int(width)}_custom")
    st.session_state.setdefault(
        f"{key_prefix}_desc_auto", st.session_state[f"{key_prefix}_desc"]
    )
    desc = st.text_input(
        "CRC Algorithm Name",
        key=f"{key_prefix}_desc",
        on_change=_on_name_change,
        help=(
            "Name for your custom CRC.  Recorded in the generated code's "
            "description/comments and used to seed the **basename** below "
            "(the same way a catalogue pick seeds it).  Defaults to "
            "`crc<width>_custom` to match the catalogue naming style."
        ),
    )

    custom_error: str | None = None
    poly, e1 = parse_hex(poly_raw, "Polynomial", int(width))
    init, e2 = parse_hex(init_raw, "Init", int(width))
    check, e3 = parse_hex(check_raw, "Check", int(width))
    xorout, e4 = parse_hex(xorout_raw, "Xorout", int(width))
    for err in (e1, e2, e3, e4):
        if err and not custom_error:
            custom_error = err

    entry: AlgorithmInfo | None = None
    if custom_error:
        st.error(custom_error)
    else:
        # If none of e1..e4 set custom_error, then poly/init/check/xorout
        # are all non-None.  The asserts narrow the types for the static
        # checker (poly et al. are int | None from parse_hex).
        assert poly is not None
        assert init is not None
        assert check is not None
        assert xorout is not None
        entry = AlgorithmInfo(
            width=int(width),
            poly=poly,
            init=init,
            refin=refin,
            refout=refout,
            xorout=xorout,
            check=check,
            desc=desc,
            source="custom",
        )

    return entry, int(width), custom_error


def render_test_vector_display(
    entry: AlgorithmInfo | None,
    is_custom: bool,
    auto_check: bool = False,
) -> None:
    """Render an inline pill showing the algorithm's CRC of ``b"123456789"``.

    Used by the Code Gen tabs as an informational signal -- no button
    click needed.  For catalog entries the computed value equals
    ``entry.check`` by construction; for custom entries it's computed
    live from the user's current parameters.  When the user is supplying
    the ``check`` field by hand (``auto_check`` False) the computed value
    is compared to it with a ✓ / ✗ badge, catching the "your params don't
    actually produce the check value you typed" case before the user
    generates code with a broken self-test.  When the check is
    auto-calculated they always agree, so the comparison is dropped.

    Args:
        entry: The :class:`AlgorithmInfo` to evaluate.  ``None`` means the
            custom form has validation errors; the function renders nothing
            in that case so it stays quiet until the user fixes things.
        is_custom: When True, computes the CRC live from ``entry``'s
            parameters.  When False, just shows the published ``entry.check``.
        auto_check: When True (custom only), the Check field is being
            auto-calculated, so the value shown *is* the check -- the badge
            says "auto-calculated" instead of comparing to a typed value.
    """
    if entry is None:
        return

    nibbles = (entry.width + 3) // 4
    # Custom path: compute live from the user's typed parameters (no
    # registered name to defer to).  Catalog path: entry.check IS the
    # test-vector CRC by definition -- no compute, just display it.
    if is_custom:
        value = generic_crc(
            b"123456789",
            entry.width,
            entry.poly,
            entry.init,
            entry.refin,
            entry.refout,
            entry.xorout,
        )
    else:
        value = entry.check
    formatted = f"0x{value:0{nibbles}X}"

    if is_custom:
        expected = f"0x{entry.check:0{nibbles}X}"
        ok = value == entry.check
        with st.container(horizontal=True, gap="small"):
            st.badge(
                f"Test vector CRC: {formatted}",
                color="green",
                icon=":material/calculate:",
                help=(
                    'The CRC of `b"123456789"` computed live from '
                    "your custom parameters."
                ),
            )
            if auto_check:
                st.badge(
                    "auto-calculated",
                    color="green",
                    icon=":material/bolt:",
                    help=(
                        "This value is the **Check** field — derived from "
                        "your parameters, so the generated `*_self_test()` "
                        "passes by construction."
                    ),
                )
            elif ok:
                st.badge(
                    "matches Check",
                    color="green",
                    icon=":material/check:",
                    help=f"Equals the **Check** value you entered: `{expected}`.",
                )
            else:
                st.badge(
                    "mismatch with Check",
                    color="red",
                    icon=":material/close:",
                    help=(
                        f"Differs from the **Check** value you entered: "
                        f"`{expected}`.  Either the parameters or the "
                        f"Check field needs adjusting."
                    ),
                )
        if auto_check:
            st.caption(
                "Computed live from your parameters by `crcglot` and used "
                "as the **Check** value baked into the generated "
                "`*_self_test()`."
            )
        else:
            st.caption(
                "Computed live from your parameters by `crcglot`.  The ✓/✗ "
                "badge compares it to the **Check** value you entered; if it "
                "matches now, the `*_self_test()` function baked into the "
                "generated code will pass after compilation."
            )
    else:
        st.badge(
            f"Test vector CRC: {formatted}",
            color="green",
            icon=":material/calculate:",
            help=(
                "The catalog's published **check** value for this "
                'algorithm -- the CRC of `b"123456789"`.'
            ),
        )
        st.caption(
            "This is the algorithm's published **check** value from the "
            "[reveng catalogue](https://reveng.sourceforge.io/crc-catalogue/all.htm).  "
            "crcglot's test suite generates code in every supported "
            "language for every algorithm, compiles and runs it, and "
            "asserts the output equals this exact value — so the emitter "
            "you're about to use is covered by an end-to-end test.  The "
            "generated code also includes a `*_self_test()` function "
            "that re-checks the same value at runtime, after your "
            "target compiler builds it."
        )


# ---------- Action sections (shared by tab bodies) ----------


def _build_symbol_preview(
    lang: str,
    names: list[str],
    symbol: str,
    is_bundle: bool,
) -> str:
    """Render the "Will produce: …" caption shown under the symbol input.

    Single-vs-bundle is the disambiguator users keep tripping over: the
    symbol field doubles as a function name in single-algo mode but is
    just a file stem in bundle mode (each bundled algorithm keeps its
    own catalogue-derived function name).  The preview line turns that
    abstract distinction into something concrete -- "your value `crc32`
    will produce these files and this function" -- so the user can see
    exactly what the field is controlling without having to read the
    help tooltip.

    Args:
        lang: crcglot language code.
        names: Algorithm names; ``[SENTINEL_CUSTOM]`` for custom mode.
        symbol: Current value of the symbol text input (stripped).
        is_bundle: Multi-algorithm catalog bundle (`len(names) > 1`).

    Returns:
        Markdown for a one-line ``st.caption``.  Empty-symbol case
        renders a "type a name above" hint so the line is never blank.
    """
    s = symbol.strip()
    if not s:
        return "_Type a name above to preview what the generator will produce._"
    # crcglot owns the per-language casing, so we render the *actual*
    # names it will emit by passing the stem through format_filename /
    # format_name rather than guessing -- e.g. Java/C# PascalCase the
    # file (`crc_bundle` -> `CrcBundle`) and camelCase identifiers.  The
    # field itself stays a raw stem; this line is where the casing shows.
    info = LANGUAGES[lang]
    filename = info.format_filename(s)
    files_md = " + ".join(f"`{filename}{ext}`" for ext in info.extensions)
    if is_bundle:
        # Bundle: each algorithm keeps its own catalogue-derived function
        # name inside the one file, cast to the target's identifier
        # convention.  Truncate at 3 to keep the line short on big bundles.
        head_funcs = [
            f"`{info.format_name(default_stem(n), kind='identifier')}`"
            for n in names[:3]
        ]
        suffix = "" if len(names) <= 3 else f", …  ({len(names)} total)"
        return (
            f"**Will produce:** ~{files_md} — one file bundling "
            f"{', '.join(head_funcs)}{suffix}."
        )
    # Single-algo (catalog or custom): the symbol drives the function name.
    return f"**Will produce:** ~{files_md} — a function named from `{s}`."


def render_generate_section(
    names: list[str],
    entry: AlgorithmInfo | None,
    widths: list[int],
    custom_error: str | None,
    is_custom: bool,
    key_prefix: str,
) -> None:
    """Render the code-generation controls and (on click) the output panes.

    Layout: target-language picker, implementation-variant picker
    (filtered by what the language supports at every selected width),
    file-basename text input, Generate button, then output panes per
    file extension when the user clicks Generate.

    Bumps ``bump_stats(lang)`` once on successful generation -- one tick
    per language used per click, independent of how many algorithms were
    bundled.  The output panes show the source code with a Download
    button per file; for multi-file languages (e.g. C emitting ``.h`` +
    ``.c``) the panes appear side-by-side.

    Args:
        names: Catalog algorithm names for catalog mode (one or several
            -- multi triggers crcglot's combiner), or ``[SENTINEL_CUSTOM]``
            for custom mode.  Empty list disables Generate (the picker
            renders a warning above this section).
        entry: :class:`AlgorithmInfo` for custom mode; ignored in catalog
            mode (where crcglot looks each name up internally).  ``None``
            triggers an error path if the user clicks Generate in custom
            mode.
        widths: Per-name widths in the same order as ``names``.  Used to
            filter which implementation variants are offered (slice8
            only at 32/64; bundling drops slice8 if any algorithm is
            narrower).
        custom_error: First validation error from the custom form, or
            ``None``.  In custom mode the Generate button is disabled while
            this is non-None.
        is_custom: Whether to dispatch through :func:`generate_custom`
            (True) or :func:`generate_catalogue` (False).
        key_prefix: Per-tab namespace for streamlit widget keys.
    """
    if not names:
        return
    is_bundle = (not is_custom) and len(names) > 1
    first_name = names[0]

    lang = (
        st.segmented_control(
            "Target language",
            list(LANGUAGES),
            format_func=lang_label,
            default="c",
            key=f"{key_prefix}_lang",
        )
        or "c"
    )

    variants = available_variants_bundle(lang, [int(w) for w in widths])

    # Help text tracks the currently-selected variant.  Labels and
    # descriptions read live from crcglot's `variant_info()` so they
    # stay in sync with the library.
    _prev_variant = st.session_state.get(f"{key_prefix}_variant_picker") or variants[0]
    if _prev_variant not in variants:
        _prev_variant = variants[0]
    _prev_variant_info = variant_info(_prev_variant)

    variant = (
        st.segmented_control(
            "Implementation",
            variants,
            format_func=variant_label,
            default=variants[0],
            key=f"{key_prefix}_variant_picker",
            help=f"{_prev_variant_info.label}: {_prev_variant_info.description}",
        )
        or variants[0]
    )
    st.caption(
        f"{variant_info(variant).description}  "
        "Speed-up figures are rough — see "
        "[crcglot's BENCHMARKS.md]"
        "(https://github.com/hucker/crcglot/blob/main/BENCHMARKS.md) "
        "for measured numbers."
    )

    # Comment style picker -- single-select, language-aware.  Always
    # rendered (even when only `plain` applies) so the UI doesn't flicker
    # as the user switches between languages.  Stale styles (e.g. doxygen
    # carried over from C to Rust) snap to the first valid style for the
    # new language; crcglot orders `plain` first in every language's
    # `.styles` tuple so the snap is deterministic.
    styles = [s.name for s in LANGUAGES[lang].styles]
    style_state_key = f"{key_prefix}_comment_style"
    prev_style = st.session_state.get(style_state_key)
    if prev_style not in styles:
        prev_style = styles[0]
    _prev_style_info = style_info(prev_style)
    comment_style = (
        st.segmented_control(
            "Comment style",
            styles,
            format_func=style_label,
            default=prev_style,
            key=style_state_key,
            help=f"{_prev_style_info.label}: {_prev_style_info.description}",
        )
        or prev_style
    )
    st.caption(style_info(comment_style).description)

    # Naming convention picker -- language-aware; defaults to whatever
    # crcglot considers idiomatic for the target (e.g. PascalCase for
    # C#, snake_case for C/Rust/Python).  Same survives-language-switch
    # pattern as comment style, with the fallback going to the new
    # language's idiomatic default rather than the first list element.
    namings = sorted(LANGUAGES[lang].naming, key=NAMING_ORDER.index)
    naming_state_key = f"{key_prefix}_naming"
    prev_naming = st.session_state.get(naming_state_key)
    if prev_naming not in namings:
        prev_naming = LANGUAGES[lang].default_naming
    _prev_naming_info = naming_info(prev_naming)

    naming = (
        st.segmented_control(
            "Naming convention",
            namings,
            format_func=lambda n: naming_info(n).label,
            default=prev_naming,
            key=naming_state_key,
            help=f"{_prev_naming_info.label}: {_prev_naming_info.description}",
        )
        or prev_naming
    )
    st.caption(naming_info(naming).description)

    # Advisories about faster-alternative paths come from crcglot itself
    # via LanguageInfo.advisories_for -- the "which language has a
    # hardware-accelerated stdlib for CRC-32" knowledge is library data,
    # not UI data, so we just consume Advisory objects and translate the
    # severity to a Streamlit affordance.  Custom mode also benefits:
    # advisories_for accepts AlgorithmInfo, so a user-typed CRC whose
    # parameters happen to equal IEEE crc32 still surfaces the
    # stdlib-crc32 advisory (the old name-based check missed this).
    if not (is_custom and entry is None):
        advisory_targets: list = [entry] if is_custom else list(names)
        for adv in LANGUAGES[lang].advisories_for(advisory_targets):
            if adv.severity == "warning":
                st.warning(adv.message)
            else:
                st.info(adv.message)

    sym_col, btn_col = st.columns([3, 1], vertical_alignment="bottom")
    # Raw, language-independent stem; crcglot owns the derivation (single
    # name vs combined bundle stem) and the per-language casing is applied
    # downstream for display and at generation.  Custom mode seeds from
    # the user's "CRC Algorithm Name" so the basename mirrors it, exactly
    # as a catalogue pick seeds the stem from the algorithm name.
    if is_custom:
        custom_name = st.session_state.get(f"{key_prefix}_desc") or "crc_custom"
        default_sym = default_stem(custom_name)
    else:
        default_sym = default_stem(names)

    sym_key = f"{key_prefix}_symbol"
    sym_auto_key = f"{key_prefix}_symbol_auto"
    # First-render seed only.  Subsequent selection changes are handled
    # by the multiselect's on_change callback
    # (_reseed_basename_on_alg_change) -- in catalog mode -- so the field
    # updates as a change notification rather than an inline
    # set-before-instantiate.  Custom mode has no multiselect, so its
    # default ("custom_crc") seeds here and never needs to track a
    # selection.
    if sym_key not in st.session_state:
        st.session_state[sym_key] = default_sym
        st.session_state[sym_auto_key] = default_sym

    with sym_col:
        # Shared guidance: the field is a language-independent *stem*;
        # crcglot re-cases it per target (PascalCase files/classes for
        # Java & C#, camelCase identifiers, snake_case elsewhere).
        # Recommending snake_case is the safe input: it round-trips
        # cleanly into every target's convention, whereas a value that's
        # already cased one way can translate oddly (e.g. `MyCrc` ->
        # Java class `Mycrc`).  The live "Will produce" line shows the
        # exact names for the current language.
        snake_tip = (
            "Write it in **snake_case** (e.g. `crc_bundle`) — that "
            "translates reliably into every target's naming "
            "convention.  See the **Will produce** line for the exact "
            "names crcglot will emit for the selected language."
        )
        if is_bundle:
            sym_label = "File basename"
            sym_help = (
                "Stem for the one bundled file (and, for Java & C#, the "
                "container class).  Each algorithm keeps its own "
                "catalogue-derived function name inside the file.  "
                f"{snake_tip}"
            )
        else:
            sym_label = "Function / file basename"
            sym_help = (
                "Stem for the generated function name (and, for C, the "
                f".c / .h filename).  {snake_tip}"
            )
        symbol = st.text_input(sym_label, key=sym_key, help=sym_help)
    with btn_col:
        go = st.button(
            "Generate code",
            type="primary",
            disabled=((not symbol.strip()) or (is_custom and custom_error is not None)),
            use_container_width=True,
            icon=":material/play_arrow:",
            key=f"{key_prefix}_go",
        )

    # Concrete preview of what the symbol value becomes -- file
    # names (always) plus function name (single-algo) or per-algo
    # function names (bundle).  Renders below the row so it doesn't
    # disturb the input/button baseline alignment.
    st.caption(_build_symbol_preview(lang, names, symbol, is_bundle))

    if go:
        try:
            if is_custom:
                # The button's `disabled=` clause above guarantees we
                # never get here with a None entry in custom mode --
                # custom_error being None means render_custom_picker
                # returned a valid AlgorithmInfo.  Asserting narrows
                # the type for the static checker.
                assert entry is not None
                files = generate_source_files(
                    lang,
                    entry=entry,
                    variant=variant,
                    symbol=symbol.strip(),
                    comment_style=comment_style,
                    naming=naming,
                )
            else:
                # Catalog mode: pass the list -- generate_source_files
                # routes single-algo vs bundle internally via crcglot.
                files = generate_source_files(
                    lang,
                    names=names,
                    variant=variant,
                    symbol=symbol.strip(),
                    comment_style=comment_style,
                    naming=naming,
                )
        except ValueError as e:
            st.error(str(e))
            st.stop()
        if not files:
            label = first_name if not is_bundle else ", ".join(names)
            st.error(f"Generator returned no output for {label!r}.")
            st.stop()
        bump_stats(lang)

        with st.container(border=True):
            st.subheader(f"View {LANGUAGES[lang].display_name} Output")
            # crcglot owns the filename and the file's role (e.g. C's
            # header vs source) -- we render what it hands back rather
            # than reconstructing `{symbol}{ext}` ourselves.
            cols = st.columns(len(files)) if len(files) > 1 else (st.container(),)
            for col, gf in zip(cols, files):
                with col:
                    role = f" · {gf.role}" if gf.role else ""
                    st.markdown(
                        f"**\U0001f4c4 `{gf.filename}`**{role}  ·  "
                        f"*{len(gf.content):,} bytes*"
                    )
                    st.code(gf.content, language=lang, line_numbers=True)
                    st.download_button(
                        f"Download {gf.filename}",
                        gf.content,
                        file_name=gf.filename,
                        mime="text/plain",
                        use_container_width=True,
                        icon=":material/download:",
                        key=f"{key_prefix}_dl_{gf.filename}",
                    )


# Calc results show a copyable "frame" (payload + trailing CRC) so the user
# can paste it straight into the Recover Custom tab and confirm the CRC
# parameters round-trip.  Capped so a large input can't dump a huge hex
# string into the result panel.
FRAME_PREVIEW_MAX_BYTES = 256


def render_calculate_section(
    name: str | None,
    entry: AlgorithmInfo | None,
    custom_error: str | None,
    key_prefix: str,
    allow_verify: bool = True,
) -> None:
    """Render the Calculate(/Verify) CRC controls.

    Layout: optional test-vector checkbox, Text/Hex input-mode segmented
    control, multi-line text area, Calculate(/Verify) button.  On click,
    parses the input via :func:`parse_hex_bytes` (Hex mode) or
    ``.encode("utf-8")`` (Text mode), computes the CRC via crcglot's
    :func:`encode_int` (catalog) or :func:`generic_crc` (custom), bumps
    :data:`CALC_KEY`, and renders the result.

    When ``allow_verify=True`` and the user has the test-vector checkbox
    checked at click time, the result also shows a ✓ Match / ✗ Mismatch
    badge comparing against ``entry.check`` (the canonical reveng check
    value).  Checking the box loads ``b"123456789"`` into the input field
    in whatever representation matches the current Input format; the user
    can then edit freely -- the button always reads from the visible field.

    Args:
        name: Catalog algorithm name (e.g. ``"crc32"``) for catalog mode,
            or ``None`` for custom mode (no registered name to dispatch
            through; falls back to :func:`generic_crc` with the typed
            parameters).  Also used as the label shown above the result.
        entry: :class:`AlgorithmInfo` to compute against.  ``None`` (or a
            non-None ``custom_error``) renders a helpful info banner
            instead of the controls.
        custom_error: First validation error from the custom form, or
            ``None``.  Same gating as ``entry``.
        key_prefix: Per-tab namespace for streamlit widget keys.
        allow_verify: When True (Catalog Calc), shows the test-vector
            checkbox and the verify badge.  When False (Custom Calc), the
            checkbox is suppressed entirely -- there's no authoritative
            check value on the custom side, so the verify badge would be
            circular.
    """
    if entry is None or custom_error is not None:
        st.info("Fix the algorithm parameters above to enable calculation.")
        return

    mode_state_key = f"{key_prefix}_input_mode"
    text_state_key = f"{key_prefix}_text"
    file_widget_key = f"{key_prefix}_file"
    file_interp_key = f"{key_prefix}_file_interp"

    # Hoist the input-format picker above the test-vector checkbox so the
    # rest of the controls (test vector, input widget, button disable) can
    # branch on it.
    mode_col, _ = st.columns([1, 3], vertical_alignment="bottom")
    with mode_col:
        input_mode = (
            st.segmented_control(
                "Input format",
                ["Text", "Hex", "File"],
                default="Text",
                key=mode_state_key,
            )
            or "Text"
        )

    # Test-vector loader only makes sense for Text/Hex — there's no input
    # field to inject `b"123456789"` into when the user has chosen File.
    use_test_vector = False
    if allow_verify and input_mode != "File":
        use_tv_key = f"{key_prefix}_use_tv"
        prev_tv_key = f"{key_prefix}_prev_tv"

        use_test_vector = st.checkbox(
            'Use test vector (b"123456789")',
            value=False,
            key=use_tv_key,
            help=(
                'Loads the canonical test bytes `"123456789"` into the '
                "input below.\n\n"
                "When checked, the computed CRC is compared against the "
                "algorithm's catalog **check** value and a ✓ / ✗ badge "
                "shows whether they agree."
            ),
        )

        # On unchecked -> checked transition, copy the test vector into the
        # input field in whatever representation matches the current mode.
        if use_test_vector and not st.session_state.get(prev_tv_key, False):
            current_mode = st.session_state.get(mode_state_key, "Text")
            if current_mode == "Hex":
                st.session_state[text_state_key] = " ".join(
                    f"{b:02x}" for b in b"123456789"
                )
            else:
                st.session_state[text_state_key] = "123456789"
        st.session_state[prev_tv_key] = use_test_vector

    if input_mode == "File":
        uploaded = st.file_uploader(
            "Input file",
            key=file_widget_key,
            help=(
                "**Raw bytes**: every byte of the uploaded file is fed to "
                "the CRC as-is.  Use for firmware images, packet captures, "
                "or any artifact you want to verify in place.\n\n"
                "**Hex dump**: the file is read as ASCII text and run "
                "through the same parser the Hex input mode uses — "
                "`0x` prefixes, `:`, `,`, and whitespace are stripped, "
                "and the remainder must be valid hex pairs.  Use for "
                "Wireshark / `xxd` / debugger output."
            ),
        )
        file_interp = (
            st.segmented_control(
                "Interpret file as",
                ["Raw bytes", "Hex dump"],
                default="Raw bytes",
                key=file_interp_key,
            )
            or "Raw bytes"
        )
        text = ""
    else:
        uploaded = None
        file_interp = "Raw bytes"
        text = st.text_area(
            "Input data",
            height=120,
            placeholder=(
                "de ad be ef\n0xCA:0xFE\n0x12, 0x34"
                if input_mode == "Hex"
                else "Type or paste any text..."
            ),
            help=(
                "**Text mode**: input is encoded as UTF-8 bytes.\n\n"
                "**Hex mode**: strips `0x` / `0X` prefixes, `:`, `,`, and "
                "whitespace, then consumes the remainder as two-nibble byte "
                "pairs.  Odd-length input or non-hex chars after stripping "
                "are rejected with a clear error."
            ),
            key=text_state_key,
        )

    _, btn_col = st.columns([3, 1], vertical_alignment="bottom")
    with btn_col:
        button_disabled = uploaded is None if input_mode == "File" else not text.strip()
        # Button label reflects what's actually about to happen: only say
        # "Verify" when verification is on (allow_verify AND test-vector
        # checkbox is checked).
        calc_go = st.button(
            "Calculate / Verify" if use_test_vector else "Calculate",
            type="primary",
            disabled=button_disabled,
            use_container_width=True,
            icon=":material/calculate:",
            key=f"{key_prefix}_go",
        )

    if not calc_go:
        return

    # File + Raw bytes is the only path that can be truly streamed --
    # feed crcglot 0.15's CrcStream a fixed-size chunk at a time so the
    # peak in-process memory is bounded by chunk_size, not file size.
    # Hex-dump interpretation needs the whole text in memory before
    # parsing anyway (hex chars span chunk boundaries), so that branch
    # stays single-shot, as do Text and Hex (textarea) modes.
    # `data` holds the payload bytes on non-streaming paths; it stays None
    # when streaming (we never buffer the whole file), which the frame
    # preview below uses to know it must skip.
    data: bytes | None = None
    streaming = input_mode == "File" and file_interp == "Raw bytes"

    if streaming:
        if name is not None and name in ALGORITHMS:
            stream = crc_stream(name)
        else:
            stream = CrcStream(
                width=entry.width,
                poly=entry.poly,
                init=entry.init,
                refin=entry.refin,
                refout=entry.refout,
                xorout=entry.xorout,
            )
        total_bytes = 0
        uploaded.seek(0)
        while True:
            chunk = uploaded.read(256 * 1024)
            if not chunk:
                break
            stream.update(chunk)
            total_bytes += len(chunk)
        value = stream.digest()
    else:
        if input_mode == "File":
            raw = uploaded.getvalue()
            try:
                data = parse_hex_bytes(raw.decode("ascii", errors="ignore"))
            except ValueError as e:
                st.error(f"Hex-dump parse error: {e}")
                return
            if not data:
                st.error("File contained no hex digits after stripping separators.")
                return
        elif input_mode == "Hex":
            try:
                data = parse_hex_bytes(text)
            except ValueError as e:
                st.error(str(e))
                return
            if not data:
                st.error("Hex input is empty after stripping separators.")
                return
        else:
            data = text.encode("utf-8")

        # Defer to crcglot: catalog algorithms compute via encode_int(name);
        # custom algorithms have no registered name so we hand crcglot the
        # raw parameter tuple from the user's typed AlgorithmInfo.
        if name is not None and name in ALGORITHMS:
            value = encode_int(data, name)
        else:
            value = generic_crc(
                data,
                entry.width,
                entry.poly,
                entry.init,
                entry.refin,
                entry.refout,
                entry.xorout,
            )
        total_bytes = len(data)

    nibbles = (entry.width + 3) // 4
    formatted = f"0x{value:0{nibbles}X}"
    bump_stats(CALC_KEY)

    label = name or entry.desc or "custom"
    with st.container(border=True):
        st.subheader("View Result")
        st.markdown(
            f"**\U0001f9ee Computed CRC**  ·  `{label}`  ·  "
            f"*{total_bytes:,} byte{'' if total_bytes == 1 else 's'} input "
            f"· {entry.width}-bit*",
        )
        st.code(formatted, language=None)

        if use_test_vector:
            expected = f"0x{entry.check:0{nibbles}X}"
            ok = value == entry.check
            if ok:
                st.badge(
                    "Match",
                    color="green",
                    icon=":material/check:",
                    help=(
                        f"Matches the catalog's published **check** value: "
                        f"`{expected}`."
                    ),
                )
            else:
                st.badge(
                    "Mismatch",
                    color="red",
                    icon=":material/close:",
                    help=(
                        f"Differs from the catalog's published **check** "
                        f"value: `{expected}`."
                    ),
                )
            st.caption(
                "Verification compares the computed CRC against the "
                "catalog's published **check** value — the canonical "
                "answer from Greg Cook's "
                "[reveng catalogue](https://reveng.sourceforge.io/crc-catalogue/all.htm)."
            )

        # Round-trip frame: payload + big-endian CRC as one hex string --
        # exactly the shape the Recover Custom tab consumes.  Paste it there
        # to confirm the CRC parameters come back out.  `data is None` means
        # the streaming path (large file) ran, so there's nothing buffered to
        # show; the byte cap keeps a big input from flooding the panel.
        if data is not None and len(data) <= FRAME_PREVIEW_MAX_BYTES:
            crc_byte_count = (entry.width + 7) // 8
            frame_hex = (data + value.to_bytes(crc_byte_count, "big")).hex(" ")
            st.markdown("**\U0001f9e9 Frame (payload + CRC)**")
            st.code(frame_hex, language=None)
            st.caption(
                f"Payload + the {entry.width}-bit CRC appended **big-endian** "
                f"({crc_byte_count} byte{'' if crc_byte_count == 1 else 's'}).  "
                "Paste into **Recover Custom** (CRC width "
                f"{crc_byte_count * 8}-bit, byte order Big).  Collect a few "
                "frames from different payloads — one alone is often "
                "underdetermined."
            )
        elif data is not None:
            st.caption(
                f"*Frame preview omitted — input is {len(data):,} bytes "
                f"(shown for inputs ≤ {FRAME_PREVIEW_MAX_BYTES} bytes).*"
            )


# ---------- Tab bodies ----------


def render_faq_tab() -> None:
    """Render the body of the FAQ / overview tab.

    A short orientation page covering what CRC101 does, why the output
    can be trusted, when to use which other tab, and the size-vs-speed
    implementation variants.  Pure markdown -- no widgets, no escape
    hatches.
    """
    if ACKNOWLEDGMENTS:
        ack_lines = "\n".join(
            f"- **[{ack['name']}]({ack['url']})** — {ack['author']}. {ack['role']}."
            for ack in ACKNOWLEDGMENTS
        )
        ack_block = (
            "### Standing on the shoulders of giants\n\n"
            "CRC101 (and the underlying "
            "[`crcglot`](https://github.com/hucker/crcglot) library) exists "
            "because of decades of public work by others.  The algorithms, "
            "parameter vocabulary, and runtime acceleration we lean on:\n\n"
            f"{ack_lines}\n\n"
            "---\n\n"
        )
    else:
        ack_block = ""
    # Reads live from crcglot so new target languages appear in the FAQ
    # without an edit here.
    _lang_names = [LANGUAGES[k].display_name for k in LANGUAGES]
    if len(_lang_names) > 1:
        faq_langs = ", ".join(_lang_names[:-1]) + ", or " + _lang_names[-1]
    else:
        faq_langs = _lang_names[0]
    with st.container(border=True):
        st.markdown(
            f"""
{ack_block}### What CRC101 does

- **Generate CRC code** in {faq_langs} — for any of
  {len(ALGORITHMS)} catalog algorithms (one at a time, or several
  bundled into one file) or a custom polynomial you define.
- **Calculate a CRC** over your own bytes (text or hex), with
  optional verification against the canonical check value.
- **Reverse-lookup** a captured CRC: paste the payload + its trailing
  CRC and find which algorithm produced it.

### Why you can trust the output

- The {len(ALGORITHMS)} algorithms come from **Greg Cook's
  [reveng catalogue](https://reveng.sourceforge.io/crc-catalogue/all.htm)**,
  the de-facto industry reference.  Each entry has a published `check`
  value — the CRC of the ASCII bytes `"123456789"`.
- The underlying library
  [`crcglot`](https://github.com/hucker/crcglot) is **end-to-end
  self-tested against the catalogue**: for every supported language
  × every algorithm, the test suite generates the code, compiles and
  runs it, and asserts the produced CRC equals the catalogue's
  `check` value.  Same author wrote the emitter and the test — but
  the assertion target (the `check` value) is the external reveng
  reference, not something we made up.
- On the Code Gen pages the test-vector CRC is shown automatically so
  you can sanity-check it against the catalogue before generating code.
- The **generated code includes a `*_self_test()` function** that
  re-asserts the check at runtime, after your target compiler builds it.

### When to use which tab

- **⚡ Catalog Code Gen** — generate catalogue-tested CRC source for a
  named standard algorithm in your target language.
- **⚡ Custom Code Gen** — design your own CRC (custom polynomial +
  init / refin / refout / xorout / check) and emit code using the
  same emitter the catalogue tests cover.
- **🧮 Catalog Calc** — calculate the CRC of arbitrary bytes for a
  standard algorithm, with optional verify against the catalogue check.
- **🧮 Custom Calc** — calculate the CRC for your own custom parameters.
- **🔍 Reverse Lookup** — given a captured packet and its trailing CRC,
  find which catalog algorithm produced it.  Handles big/little
  endianness, optional `0x` prefix on the CRC, trailing whitespace, etc.

### Size vs speed

Most languages let you pick the implementation variant:

- **◯ Bit-by-bit** — smallest code; ~8 ops per byte.  Use for
  size-constrained targets.
- **▦ Table-driven** — 256-entry LUT; expect roughly **2-4× faster**
  than bit-by-bit in practice.  Best general-purpose choice.
- **▩ Slice-by-8** — 8 LUTs; expect another roughly **2-4× faster**
  on top of table-driven (CRC-32 / CRC-64 only).  Best for
  high-throughput.

Numbers depend on target language, compiler, CPU, and input size --
see crcglot's
[BENCHMARKS.md](https://github.com/hucker/crcglot/blob/main/BENCHMARKS.md)
for measured figures.

VHDL and Verilog emit bit-by-bit only (the table variants don't map
cleanly onto an HDL register-transfer description).

---

Powered by [`crcglot`](https://github.com/hucker/crcglot) (the library)
and [reveng](https://reveng.sourceforge.io/crc-catalogue/all.htm)
(the catalogue).
            """
        )


def render_calc_tab(picker_kind: str, key_prefix: str, allow_verify: bool) -> None:
    """Render the body of a Calculate tab (Catalog or Custom).

    Composes :func:`render_standard_picker` *or* :func:`render_custom_picker`
    with :func:`render_calculate_section`.

    Args:
        picker_kind: ``"catalog"`` to use the catalog selectbox, ``"custom"``
            to use the 4x2 form.
        key_prefix: Per-tab namespace for streamlit widget keys
            (e.g. ``"cat_calc"`` or ``"cust_calc"``).
        allow_verify: Forwarded to :func:`render_calculate_section`.  Pass
            True for Catalog Calc (test-vector verify available), False for
            Custom Calc (no authoritative check value).
    """
    with st.container(border=True):
        if picker_kind == "catalog":
            st.subheader("Select Algorithm")
            name, entry, _ = render_standard_picker(key_prefix)
            custom_error = None
        else:
            st.subheader("Select Parameters")
            entry, _, custom_error = render_custom_picker(key_prefix)
            name = None

    with st.container(border=True):
        title = "Calculate/Verify CRC" if allow_verify else "Calculate CRC"
        st.subheader(title)
        render_calculate_section(
            name=name,
            entry=entry,
            custom_error=custom_error,
            key_prefix=key_prefix,
            allow_verify=allow_verify,
        )


def render_gen_tab(picker_kind: str, key_prefix: str, is_custom: bool) -> None:
    """Render the body of a Code Gen tab (Catalog or Custom).

    Composes :func:`render_standard_picker` *or* :func:`render_custom_picker`
    with :func:`render_test_vector_display` (between picker and Generate
    controls) and :func:`render_generate_section`.

    The test-vector display is the "show the CRC automatically" feature:
    no button click needed -- the user sees what value the algorithm
    produces for ``b"123456789"`` the moment the parameters are valid.

    Args:
        picker_kind: ``"catalog"`` to use the catalog selectbox, ``"custom"``
            to use the 4x2 form.
        key_prefix: Per-tab namespace for streamlit widget keys
            (e.g. ``"cat_gen"`` or ``"cust_gen"``).
        is_custom: Forwarded to :func:`render_test_vector_display` and
            :func:`render_generate_section`.  True for Custom Code Gen,
            False for Catalog Code Gen.
    """
    with st.container(border=True):
        if picker_kind == "catalog":
            # Catalog Code Gen uses the multi-select picker so the user
            # can ask crcglot to bundle several algorithms into one
            # generated file (0.12 feature).  Single-algo behavior is
            # preserved: with one selection the picker shows the same
            # parameter table the selectbox picker would have.
            st.subheader("Select Algorithm(s)")
            names, entry, widths = render_multi_standard_picker(key_prefix)
            custom_error = None
        else:
            st.subheader("Select Parameters")
            entry, width, custom_error = render_custom_picker(key_prefix)
            names = [SENTINEL_CUSTOM]
            widths = [int(width)]
        # Test vector pill makes sense for exactly one algorithm: catalog
        # entries have a published check value; custom entries compute it
        # live.  In multi-algo bundles every algorithm carries its own
        # catalog check value -- showing one would mislead, listing them
        # all would dominate the viewport, so we collapse to a caption.
        if is_custom or len(names) == 1:
            render_test_vector_display(
                entry,
                is_custom=is_custom,
                auto_check=is_custom
                and st.session_state.get(f"{key_prefix}_auto_check", True),
            )
        else:
            st.caption(
                f"Bundling **{len(names)}** algorithms — each carries "
                "its own catalogue **check** value and an embedded "
                "`*_self_test()` that re-asserts it at runtime."
            )

    with st.container(border=True):
        st.subheader("Generate code")
        render_generate_section(
            names=names,
            entry=entry,
            widths=widths,
            custom_error=custom_error,
            is_custom=is_custom,
            key_prefix=key_prefix,
        )


def render_reverse_tab() -> None:
    """Render the body of the Reverse Lookup tab.

    Both workflows fully delegate the catalog search to ``crcglot.detect``
    via :func:`crc_lib.detect_chunk`.  Two workflows, selected via the
    "CRC source" segmented control:

        - **Use Target**: the user supplies a payload *and* the target
          CRC value separately; ``detect`` is called with ``target_crc``
          which loops the catalog comparing each algorithm's CRC of the
          payload against the target.  No byte interpretation happens in
          this path, so all matches report ``Endian: Big``.
        - **End-of-data** (Any / 8 / 16 / 32 / 64 bits): the trailing
          bytes-or-hex of the input *are* the CRC; ``detect`` figures
          out the boundary, tries both endianness, and (in text mode)
          handles ``0x`` prefixes, uppercase, and separators
          automatically.  The width buttons translate to ``detect``'s
          ``algorithms="crc<W>*"`` glob.

    On click, bumps :data:`REVERSE_KEY`.  Each match renders as a green
    ✓ pill with the algorithm name; little-endian matches get an
    additional amber ↔ pill.
    """
    rev_go = False
    rev_input_mode = "Text"
    rev_text = ""
    rev_target_raw = ""

    with st.container(border=True):
        st.subheader("Identify")
        st.caption(
            f"Have a captured payload and its trailing CRC but don't know "
            f"which algorithm produced it?  Paste both below and the "
            f"{len(ALGORITHMS)}-algorithm catalog is searched for matches.  "
            "Endianness, `0x` prefixes, uppercase hex, and separators are "
            "handled automatically by crcglot's `detect()`."
        )

        mode_col, _ = st.columns([1, 2], vertical_alignment="bottom")
        with mode_col:
            rev_input_mode = (
                st.segmented_control(
                    "Input format",
                    ["Text", "Hex"],
                    default="Text",
                    key="rev_input_mode",
                )
                or "Text"
            )

        # CRC source: either treat the trailing bytes/chars of the input
        # as the CRC and let detect() find the boundary (Any / per-width),
        # or supply the target value separately (Target -- last in the
        # list since detect() handles the common cases).
        rev_source = (
            st.segmented_control(
                "CRC source",
                ["Any", "8", "16", "32", "64", "Target"],
                default="Any",
                key="rev_source",
                format_func=lambda s: (
                    "Use Target"
                    if s == "Target"
                    else "Detect (any width)"
                    if s == "Any"
                    else f"{s}-bit at end"
                ),
                help=(
                    "**Where does the CRC come from?**\n\n"
                    "- **Detect (any width)** — the trailing bytes/chars of the "
                    "input *are* the CRC.  `detect()` searches every catalog "
                    "algorithm at every width.\n"
                    "- **8 / 16 / 32 / 64** — same, restricted to algorithms "
                    "of that width via the `crc<W>*` glob.\n"
                    "- **Use Target** — type the CRC value into a separate "
                    "field; the input is the payload only.\n\n"
                    "In all end-of-data modes both byte orders are tried "
                    "automatically."
                ),
            )
            or "Any"
        )
        end_of_data = rev_source != "Target"
        end_width = int(rev_source) if rev_source not in ("Target", "Any") else 0

        if not end_of_data:
            rev_target_raw = st.text_input(
                "Target CRC (hex)",
                placeholder="0xcbf43926",
                help=(
                    "The CRC value you're trying to match.  Up to 64 "
                    "bits.  Both byte orderings are tried automatically: "
                    "matches that hit on the byte-reversed reading of "
                    "the value come back flagged with `Endian: Little` "
                    "so you can see when the protocol's wire format is "
                    "little-endian."
                ),
                key="rev_target",
            )
        else:
            rev_target_raw = ""

        if end_of_data and rev_input_mode == "Text":
            _input_label = (
                "Input data (payload + trailing hex CRC; framing detected "
                "automatically)"
            )
        elif end_of_data:
            _input_label = (
                "Input data (payload + trailing CRC bytes; framing detected "
                "automatically)"
            )
        else:
            _input_label = "Input data (bytes that produced the CRC)"

        rev_text = st.text_area(
            _input_label,
            height=120,
            placeholder=(
                "de ad be ef\n0xCA:0xFE\n0x12, 0x34"
                if rev_input_mode == "Hex"
                else "Type or paste any text..."
            ),
            help=(
                "Hex mode strips 0x/0X prefixes, ':', ',' and whitespace, "
                "then consumes the rest as two-nibble byte pairs."
            ),
            key="rev_text",
        )

        target_required = not end_of_data
        _, rev_btn_col = st.columns([3, 1], vertical_alignment="bottom")
        with rev_btn_col:
            rev_go = st.button(
                "Identify",
                type="primary",
                disabled=(
                    not rev_text.strip()
                    or (target_required and not rev_target_raw.strip())
                ),
                use_container_width=True,
                icon=":material/search:",
            )

    if not rev_go:
        return

    # Dispatch -- end-of-data delegates the whole framing problem to
    # detect_chunk; Target mode keeps the catalog search since its
    # shape (separate target + payload) doesn't fit detect().
    if end_of_data:
        # The Text/Hex toggle maps straight to crcglot's mode: 'text'
        # means "literal payload + trailing hex CRC" framing, 'hex'
        # means "the whole input is hex-encoded bytes, strip separators
        # and decode."  crcglot does the decoding/framing itself for
        # both -- no local parse_hex_bytes step needed.
        detect_mode = "hex" if rev_input_mode == "Hex" else "text"
        try:
            matches = detect_chunk(
                rev_text,
                width=end_width or None,
                mode=detect_mode,
            )
        except ValueError as e:
            st.error(f"Input data: {e}")
            st.stop()
        input_summary = (
            f"{len(rev_text):,} char {rev_input_mode.lower()} input · "
            f"{'any width' if end_width == 0 else f'{end_width}-bit'}"
        )
        no_match_target_display = (
            f"this input under "
            f"{'any catalog width' if end_width == 0 else f'width {end_width}'}"
        )

    else:
        # Target mode -- the user supplies the CRC value separately;
        # the whole input is the payload.  Deferred to crcglot's
        # detect(target_crc=...) which loops the catalog itself,
        # respects the algorithms glob, and reports endianness as
        # "Big" by convention (no byte parsing happens in this path).
        target, target_err = parse_hex(rev_target_raw, "Target CRC", 64)
        if target_err:
            st.error(target_err)
            st.stop()
        assert target is not None
        detect_mode = "hex" if rev_input_mode == "Hex" else "text"
        try:
            matches = detect_chunk(
                rev_text,
                mode=detect_mode,
                target_crc=target,
            )
        except ValueError as e:
            st.error(f"Input data: {e}")
            st.stop()
        target_display = f"0x{target:X}"
        input_summary = (
            f"{len(rev_text):,} char {rev_input_mode.lower()} payload · "
            f"target `{target_display}`"
        )
        no_match_target_display = f"`{target_display}`"

    bump_stats(REVERSE_KEY)

    with st.container(border=True):
        st.subheader(
            "View Result",
            help=(
                "**What each match pill means** "
                "(click any pill for its own tooltip):\n\n"
                "- **green ✓ name** — the matched catalog algorithm.\n"
                "- **Width** — the CRC's bit width (8 / 16 / 32 / 64).\n"
                "- **Endian** — byte order used to read the trailing CRC "
                "bytes.  **Big** is the natural / network-order reading "
                "(most common).  **Little** means the bytes were "
                "byte-reversed before they matched.\n"
                "- **Sep** — character `detect()` found between the "
                "payload and the hex CRC in the input.\n"
                "- **Prefix** — a hex prefix (typically `0x`) detected "
                "immediately before the CRC.\n"
                "- **Hex** — case of the CRC's hex digits in the input.\n\n"
                "*Sep / Prefix / Hex only appear for Text-mode matches; "
                "Binary and Target modes have no boundary ambiguity.*"
            ),
        )

        if matches:
            plural = "es" if len(matches) != 1 else ""
            st.markdown(
                f"**\U0001f50d Found {len(matches)} match{plural}**  "
                f"·  *{input_summary}*"
            )
            for name, info, endian, padding in matches:
                # Row 1: the green algorithm-name badge (the "we found
                # it" anchor for this match).
                st.badge(
                    name,
                    color="green",
                    icon=":material/check:",
                    help="The matched catalog algorithm name.",
                )
                # Row 2: horizontal row of neutral metadata badges, each
                # carrying its own click-tooltip.  Width / Endian always
                # shown; Sep / Prefix / Hex come from detect()'s padding
                # info and only appear for Text-mode matches.
                with st.container(horizontal=True, gap="small"):
                    st.badge(
                        f"Width: {info.width}",
                        color="gray",
                        help="The CRC's bit width in bits.",
                    )
                    st.badge(
                        f"Endian: {endian}",
                        color="gray",
                        help=(
                            "Byte order used to read the trailing CRC "
                            "bytes.\n\n"
                            "- **Big** = natural / network-order reading "
                            "(most common).\n"
                            "- **Little** = byte-reversed; common when a "
                            "protocol serializes the CRC little-endian "
                            "on the wire."
                        ),
                    )
                    for label, pill_help in padding_pills(padding):
                        st.badge(label, color="gray", help=pill_help)
                if info.desc:
                    st.caption(info.desc)
        else:
            st.warning(
                f"No catalog algorithm produces {no_match_target_display} "
                f"for this input.\n\n"
                "Common reasons:\n"
                "- Custom polynomial (not in the reveng catalogue)\n"
                "- Input bytes don't exactly match the captured payload "
                "(extra/missing header bytes, trailing checksum included, etc.)\n"
                "- The checksum isn't a CRC (could be Adler-32, Fletcher, "
                "truncated hash, etc.)"
            )


def render_recover_tab() -> None:
    """Render the body of the Recover Custom CRC tab.

    Reverse-engineers an *unknown / custom* CRC from one or more sample
    frames, delegating the entire parameter search to
    :func:`crc_lib.recover_packets` (a thin wrapper over
    ``crcglot.reverse_packets``).  This is the counterpart to the
    Identify tab: Identify *matches* a known catalogue algorithm; this
    tab *recovers* arbitrary ``poly`` / ``init`` / ``refin`` /
    ``refout`` / ``xorout`` parameters that need not be catalogued.

    The layout is deliberately fixed -- no control shows or hides
    another section as it changes.  The "underdetermined -- add another
    frame" loop is served by the result message updating below a form
    that stays put, not by rearranging the inputs.

    On a successful click, bumps :data:`RECOVER_KEY`.
    """
    rec_go = False
    rec_text = ""

    with st.container(border=True):
        st.subheader("Recover a Custom CRC")
        st.caption(
            "Captured whole frames (payload + trailing CRC) from a device or "
            "protocol whose CRC *isn't* a catalogue algorithm?  Paste them "
            "below -- one hex frame per line -- and crcglot's "
            "`reverse_packets()` solves for the parameters "
            "(`poly` / `init` / `refin` / `refout` / `xorout`).  "
            "**Favor several frames of the *same* length** — that's what pins "
            "the polynomial — and include **at least two different lengths** so "
            "`init` and `xorout` can be separated.  Frames that are *all* "
            "different lengths usually can't be solved."
        )

        rec_text = st.text_area(
            "Sample frames — one hex frame per line (payload + trailing CRC)",
            height=140,
            placeholder=(
                "de ad be ef 1d 0f\nca fe ba be 7c a1\n0x01,0x02,0x03,0x04,0x9b,0x22"
            ),
            help=(
                "Each line is one captured frame: payload followed by its "
                "trailing CRC bytes.  `0x` prefixes, `:` / `,` separators "
                "and whitespace are stripped before decoding.\n\n"
                "**Frame shape matters more than count.**  Give a few frames "
                "of the *same* length (varying the *content*, not just "
                "appending bytes), plus a second group at a different length.  "
                "4–6 frames across two lengths is usually plenty; frames that "
                "are each a different length can't pin the polynomial."
            ),
            key="rec_frames",
        )

        width_col, order_col = st.columns(2, vertical_alignment="bottom")
        with width_col:
            rec_width_label = (
                st.segmented_control(
                    "CRC width",
                    ["All", "8", "16", "32", "64"],
                    default="All",
                    format_func=lambda s: "All widths" if s == "All" else f"{s}-bit",
                    key="rec_crc_bytes",
                    help=(
                        "How many trailing bytes of each frame are the CRC "
                        "field.  **All widths** lets crcglot search every "
                        "width -- the right default when you don't already "
                        "know the CRC size; narrow it only to speed things "
                        "up or break a tie."
                    ),
                )
                or "All"
            )
        # "All" -> None (crcglot searches every width); a bit-width label maps
        # to its trailing byte count for the crc_bytes filter.
        bits_to_bytes = {"8": 1, "16": 2, "32": 4, "64": 8}
        rec_crc_bytes = bits_to_bytes.get(rec_width_label)
        with order_col:
            rec_order_label = (
                st.segmented_control(
                    "CRC byte order",
                    ["Big", "Little", "Both"],
                    default="Big",
                    key="rec_order",
                    # A 1-byte CRC has no byte order, so this is moot at 8-bit.
                    disabled=rec_width_label == "8",
                    help=(
                        "How the trailing CRC bytes are ordered on the wire.  "
                        "Example for a 2-byte CRC value `0xAABB`:\n\n"
                        "- **Big** — bytes are `AA BB` (most-significant first; "
                        "this is 'network order' and by far the most common).\n"
                        "- **Little** — bytes are `BB AA` (least-significant "
                        "first; byte-reversed).\n"
                        "- **Both** — try each ordering and report which hit.\n\n"
                        "An 8-bit (1-byte) CRC has no byte order, so this "
                        "control is disabled when CRC width is 8-bit."
                    ),
                )
                or "Big"
            )
        # Map the display label to crcglot's lowercase literal in branches so
        # the type narrows to the Literal reverse_packets expects.
        if rec_order_label == "Little":
            rec_order = "little"
        elif rec_order_label == "Both":
            rec_order = "both"
        else:
            rec_order = "big"

        rec_std_only = st.checkbox(
            "Restrict to catalogue algorithms only",
            value=False,
            key="rec_std_only",
            help=(
                "Off (default): solve for fully custom parameters -- the point "
                "of this tab.  On: only accept a solution that is a known "
                "catalogue algorithm (the **Identify** tab is simpler if "
                "that's all you need)."
            ),
        )

        _, rec_btn_col = st.columns([3, 1], vertical_alignment="bottom")
        with rec_btn_col:
            rec_go = st.button(
                "Recover CRC",
                type="primary",
                disabled=not rec_text.strip(),
                use_container_width=True,
                icon=":material/extension:",
            )

    if not rec_go:
        return

    # Delegate the whole search to crcglot; we only surface its result.
    try:
        result = recover_packets(
            rec_text,
            crc_bytes=rec_crc_bytes,
            crc_byte_order=rec_order,
            std_algo_only=rec_std_only,
        )
    except ValueError as e:
        st.error(f"Sample frames: {e}")
        st.stop()

    bump_stats(RECOVER_KEY)

    with st.container(border=True):
        st.subheader("Recovered Parameters")

        if not result.candidates:
            width_hint = (
                "all widths were searched, so the size isn't the issue"
                if rec_crc_bytes is None
                else f"is the trailing field really {rec_crc_bytes * 8}-bit?"
            )
            st.warning(
                f"{result.note}\n\n"
                "No CRC parameters fit every frame.  Things to check:\n"
                f"- **CRC width** — {width_hint}\n"
                "- **Byte order** — try **Both** if you're unsure.\n"
                "- **Frame boundaries** — each line must be exactly payload + "
                "CRC, with no extra header/trailer bytes.\n"
                "- Add **more frames** — one short frame rarely pins a CRC down."
            )
            return

        ambiguous = result.ambiguity_bits > 0 or len(result.candidates) > 1
        if ambiguous:
            st.warning(
                f"**Underdetermined.**  {result.note}  "
                "Add another sample frame to narrow it down."
            )
        else:
            st.success(result.note or "Recovered a unique parameter set.")

        # `validated_frames` is a hold-out cross-check, not a frame count:
        # crcglot re-solves from all-but-one frame and tests whether the model
        # predicts the one it held back (1 = yes, 0 = no, -1 = didn't run with
        # <4 frames).  A 0 already appends a WARNING to `note` above, so we
        # only add the positive confirmation here.
        if result.validated_frames >= 1:
            n_frames = sum(1 for line in rec_text.splitlines() if line.strip())
            st.caption(
                f"✓ Cross-checked — re-solved from {n_frames - 1} of your "
                f"{n_frames} frames and correctly predicted the held-out one "
                "(empirical confidence the model generalises, not just fits "
                "the frames it was given)."
            )

        if result.catalogue_name:
            st.info(
                f"These parameters match the known algorithm "
                f"**{result.catalogue_name}** — the \U0001f50d **Identify** "
                "tab confirms catalogue matches directly."
            )

        for info in result.candidates:
            # Anchor badge then a horizontal row of the recovered parameter
            # pills.  The headline must NOT masquerade as a catalogue match:
            # a green check + a "crcNN"-style name reads as "this is the
            # standard crcNN", which is wrong for a recovered custom poly.
            # So green check + catalogue name ONLY when crcglot actually
            # matched the catalogue; otherwise a distinct "custom" badge.
            if result.catalogue_name:
                st.badge(
                    result.catalogue_name,
                    color="green",
                    icon=":material/check:",
                    help="The recovered parameters match this catalogue algorithm.",
                )
            else:
                st.badge(
                    f"Custom {info.width}-bit CRC",
                    color="violet",
                    icon=":material/build:",
                    help=(
                        "A custom CRC — these parameters reproduce your frames "
                        "but don't match any catalogue algorithm."
                    ),
                )
            with st.container(horizontal=True, gap="small"):
                st.badge(
                    f"Width: {info.width}", color="gray", help="CRC width in bits."
                )
                st.badge(
                    f"Poly: 0x{info.poly:X}",
                    color="gray",
                    help="Generator polynomial.",
                )
                st.badge(
                    f"Init: 0x{info.init:X}",
                    color="gray",
                    help="Initial register value.",
                )
                st.badge(
                    f"RefIn: {info.refin}", color="gray", help="Reflect input bytes."
                )
                st.badge(
                    f"RefOut: {info.refout}",
                    color="gray",
                    help="Reflect output CRC.",
                )
                st.badge(
                    f"XorOut: 0x{info.xorout:X}", color="gray", help="Final XOR mask."
                )
            if info.desc:
                st.caption(info.desc)


def render_footer() -> None:
    """Render the page footer: stats counters + build info.

    Two stacked rows:
        1. Counter totals line: ``"N generations · M calculations · K
           searches · J recoveries"`` in orange.
        2. Pill row: one pill per crcglot language (per-language generation
           count) plus a 🧮 Calculate pill, a 🔍 Identify pill, and a 🧩
           Recover pill.  Zero-count pills are dimmed.

    Below that, a small monospace build line: app version + git rev (linked
    to the GitHub commit) + crcglot version (linked to PyPI).
    """
    st.divider()
    stats = load_stats()
    gen_total = sum(v for k, v in stats.items() if not k.startswith("__"))
    calc_total = stats.get(CALC_KEY, 0)
    rev_total = stats.get(REVERSE_KEY, 0)
    rec_total = stats.get(RECOVER_KEY, 0)

    st.caption(
        f"**{gen_total} generation{'' if gen_total == 1 else 's'}**"
        f" · **{calc_total} calculation{'' if calc_total == 1 else 's'}**"
        f" · **{rev_total} search{'' if rev_total == 1 else 'es'}**"
        f" · **{rec_total} recover{'y' if rec_total == 1 else 'ies'}**"
    )
    with st.container(horizontal=True, gap="small"):
        for code, info in LANGUAGES.items():
            count = stats.get(code, 0)
            st.badge(
                f"{info.emoji} {info.display_name}: {count}",
                color="gray",
                help=(
                    f"Number of times someone generated CRC code in "
                    f"{info.display_name} via this app."
                ),
            )
        st.badge(
            f"\U0001f9ee Calculate: {calc_total}",
            color="gray",
            help="Number of times someone clicked **Calculate** in either Calc tab.",
        )
        st.badge(
            f"\U0001f50d Identify: {rev_total}",
            color="gray",
            help="Number of times someone clicked **Identify** (catalogue match).",
        )
        st.badge(
            f"\U0001f9e9 Recover: {rec_total}",
            color="gray",
            help="Number of times someone clicked **Recover CRC** (custom reverse-engineer).",
        )

    rev = git_revision()
    rev_sha = rev[: -len("-dirty")] if rev.endswith("-dirty") else rev
    rev_link = (
        f'<a href="{REPO_URL}/commit/{rev_sha}" target="_blank">{rev}</a>'
        if rev != "unknown"
        else rev
    )
    crcglot_ver = crcglot_version()
    crcglot_link = (
        f'<a href="https://pypi.org/project/crcglot/{crcglot_ver}/" target="_blank">'
        f"crcglot {crcglot_ver}</a>"
        if crcglot_ver != "unknown"
        else f"crcglot {crcglot_ver}"
    )
    st.markdown(
        f'<div class="crc-build">'
        f"v{app_version()} &middot; rev {rev_link} &middot; {crcglot_link}"
        f"</div>",
        unsafe_allow_html=True,
    )
