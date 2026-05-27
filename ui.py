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

from dataclasses import asdict

import streamlit as st

from crc_lib import (
    ALGORITHMS,
    AlgorithmInfo,
    CALC_KEY,
    LANGUAGES,
    REPO_URL,
    REVERSE_KEY,
    SENTINEL_CUSTOM,
    VARIANTS,
    _crc_compute,
    alg_label,
    app_version,
    available_variants,
    bump_stats,
    catalogue_names,
    crcglot_version,
    default_symbol,
    find_matching_algorithms,
    find_matching_algorithms_at_end,
    find_matching_algorithms_text_end,
    generate_catalogue,
    generate_custom,
    git_revision,
    lang_label,
    load_stats,
    parse_hex,
    parse_hex_bytes,
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
    st.markdown(
        """
<meta name="description" content="CRC101 -- generate and verify CRCs in your browser. Catalog of 70+ algorithms, code emitters for C, Python, Rust, VHDL, C#, Go, and Zig, plus an interactive calculator.">
<meta name="keywords" content="CRC, CRC-8, CRC-16, CRC-32, CRC-64, CRC calculator, CRC code generator, cyclic redundancy check, reveng catalogue, polynomial, crcglot, C, Python, Rust, VHDL, C#, Go, Zig">
<meta name="author" content="Chuck Bass / acrocad.net">
<meta name="robots" content="index, follow">

<meta property="og:title" content="CRC101 -- CRC code generator & calculator">
<meta property="og:description" content="Generate CRC code in C, Python, Rust, VHDL, C#, Go, or Zig from 70+ catalog algorithms -- or calculate a CRC over your own bytes.">
<meta property="og:type" content="website">

<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="CRC101 -- CRC code generator & calculator">
<meta name="twitter:description" content="Generate CRC code in C, Python, Rust, VHDL, C#, Go, or Zig from 70+ catalog algorithms -- or calculate a CRC over your own bytes.">
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

    .crc-stats {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 0.4rem;
        padding-top: 0.4rem;
    }
    .crc-stats-totals {
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: #FF6B35;
        padding-top: 0.6rem;
    }
    .crc-stats-total {
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: #FF6B35;
        margin-right: 0.3rem;
    }
    .crc-stat-pill {
        display: inline-flex;
        align-items: center;
        gap: 0.3rem;
        padding: 0.15rem 0.6rem;
        font-size: 0.82rem;
        background: #FAFAFA;
        border: 1px solid #E5E7EB;
        border-radius: 999px;
    }
    .crc-stat-pill-zero { opacity: 0.45; }
    .crc-stat-pill strong { color: #FF6B35; font-weight: 700; }

    .crc-match-ok {
        color: #047857;
        background: rgba(16, 185, 129, 0.10);
        border-color: #A7F3D0;
        font-weight: 600;
    }
    .crc-match-fail {
        color: #B91C1C;
        background: rgba(239, 68, 68, 0.10);
        border-color: #FECACA;
        font-weight: 600;
    }
    /* Spacer for secondary annotation pills (e.g. endianness, width)
       that sit right of the primary algorithm-name pill. */
    .crc-annotation-pill {
        margin-left: 0.35rem;
    }
    .crc-match-expected {
        margin-left: 0.5rem;
        font-size: 0.85rem;
        opacity: 0.7;
    }
    .crc-match-expected code {
        background: #FAFAFA;
        border: 1px solid #E5E7EB;
        border-radius: 4px;
        padding: 0.05rem 0.35rem;
        font-size: 0.85rem;
    }

    .crc-section {
        display: inline-block;
        padding: 0.15rem 0.6rem;
        margin-bottom: 0.6rem;
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.07em;
        text-transform: uppercase;
        color: #FF6B35;
        background: rgba(255, 107, 53, 0.10);
        border-radius: 999px;
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

    with st.expander("All parameters"):
        st.json({
            k: (f"0x{v:X}" if isinstance(v, int) and k != "width" else v)
            for k, v in asdict(entry).items()
        })

    return name, entry, entry.width


def render_custom_picker(
    key_prefix: str,
) -> tuple[AlgorithmInfo | None, int, str | None]:
    """Render the 4x2 custom-parameter form.

    Form layout:
        - Row 1: Refin checkbox | Width number-input | Polynomial hex |
            Init hex.
        - Row 2: Refout checkbox | Check hex | Xorout hex | (empty cell).
        - Below: a Description text-input that becomes the
            :class:`AlgorithmInfo`'s ``name`` (and the function name in
            generated code).

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

    seed = ALGORITHMS[st.session_state[state_key]]
    st.caption(
        f"Custom parameters — seeded from "
        f"`{st.session_state[state_key]}`. "
        "All hex fields accept `0x...` or bare hex (e.g. `1021`)."
    )

    # 4-column x 2-row grid so every cell has the same width.
    # Row 1: Refin   | Width | Polynomial | Init
    # Row 2: Refout  | Check | Xorout     | (empty)
    with st.container(key=f"{key_prefix}_custom-grid"):
        r1c1, r1c2, r1c3, r1c4 = st.columns(4, vertical_alignment="bottom")
        with r1c1:
            refin = st.checkbox(
                "Reflect input (refin)", value=seed.refin,
                key=f"{key_prefix}_refin",
            )
        with r1c2:
            width = st.number_input(
                "Width (bits)",
                min_value=1, max_value=64,
                value=int(seed.width),
                step=1,
                key=f"{key_prefix}_width",
                help="CRC register width, 1-64 bits.",
            )
        with r1c3:
            poly_raw = st.text_input(
                "Polynomial (hex)", value=f"0x{seed.poly:X}",
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
                "Init (hex)", value=f"0x{seed.init:X}",
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
                "Reflect output (refout)", value=seed.refout,
                key=f"{key_prefix}_refout",
            )
        with r2c2:
            check_raw = st.text_input(
                "Check (hex)",
                value=f"0x{seed.check:X}",
                key=f"{key_prefix}_check",
                help=(
                    "**Test-vector check value** — the CRC of the ASCII "
                    "bytes `\"123456789\"`.  Used by the generated "
                    "self-test and (in Code Gen) compared live against "
                    "what the current parameters actually produce."
                ),
            )
        with r2c3:
            xorout_raw = st.text_input(
                "Xorout (hex)", value=f"0x{seed.xorout:X}",
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
            st.markdown(
                '<div class="crc-grid-empty"></div>', unsafe_allow_html=True,
            )

    desc = st.text_input(
        "Description",
        value="custom",
        key=f"{key_prefix}_desc",
        help=(
            "**Algorithm name** used in generated code (function names, "
            "comments).  Hyphens are converted to underscores automatically."
        ),
    )

    custom_error: str | None = None
    poly,   e1 = parse_hex(poly_raw,   "Polynomial", int(width))
    init,   e2 = parse_hex(init_raw,   "Init",       int(width))
    check,  e3 = parse_hex(check_raw,  "Check",      int(width))
    xorout, e4 = parse_hex(xorout_raw, "Xorout",     int(width))
    for err in (e1, e2, e3, e4):
        if err and not custom_error:
            custom_error = err

    entry: AlgorithmInfo | None = None
    if custom_error:
        st.error(custom_error)
    else:
        entry = AlgorithmInfo(
            name=desc or "custom", width=int(width),
            poly=poly, init=init,
            refin=refin, refout=refout,
            xorout=xorout, check=check, desc=desc,
        )

    return entry, int(width), custom_error


def render_test_vector_display(
    entry: AlgorithmInfo | None,
    is_custom: bool,
) -> None:
    """Render an inline pill showing the algorithm's CRC of ``b"123456789"``.

    Used by the Code Gen tabs as an informational signal -- no button
    click needed.  For catalog entries the computed value equals
    ``entry.check`` by construction; for custom entries it's computed
    live from the user's current parameters and compared to the typed
    ``check`` field, with a ✓ / ✗ badge.  This catches the "your params
    don't actually produce the check value you typed" case before the
    user generates code with a broken self-test.

    Args:
        entry: The :class:`AlgorithmInfo` to evaluate.  ``None`` means the
            custom form has validation errors; the function renders nothing
            in that case so it stays quiet until the user fixes things.
        is_custom: When True, renders the verify badge against
            ``entry.check``.  When False, just shows the computed CRC.
    """
    if entry is None:
        return

    value = _crc_compute(
        b"123456789", entry.width, entry.poly, entry.init,
        entry.refin, entry.refout, entry.xorout,
    )
    nibbles = (entry.width + 3) // 4
    formatted = f"0x{value:0{nibbles}X}"

    if is_custom:
        expected = f"0x{entry.check:0{nibbles}X}"
        ok = value == entry.check
        badge_cls = "crc-match-ok" if ok else "crc-match-fail"
        badge_text = "✓ matches Check" if ok else "✗ mismatch with typed Check"
        st.markdown(
            f'<span class="crc-stat-pill crc-match-ok">'
            f'\U0001F9EE Test vector CRC: <code>{formatted}</code></span>'
            f'<span class="crc-stat-pill {badge_cls}" '
            f'style="margin-left: 0.35rem;">{badge_text}</span>'
            f'<span class="crc-match-expected">'
            f'typed Check: <code>{expected}</code></span>',
            unsafe_allow_html=True,
        )
        st.caption(
            "Computed live from your parameters by crcglot's verified "
            "engine.  The ✓/✗ badge compares it to the **Check** value "
            "you typed; if it matches now, the `*_self_test()` function "
            "baked into the generated code will pass after compilation."
        )
    else:
        st.markdown(
            f'<span class="crc-stat-pill crc-match-ok">'
            f'\U0001F9EE Test vector CRC: <code>{formatted}</code></span>',
            unsafe_allow_html=True,
        )
        st.caption(
            "This is the algorithm's published **check** value from the "
            "[reveng catalogue](https://reveng.sourceforge.io/crc-catalogue/all.htm).  "
            "crcglot's code generators are independently verified to "
            "produce it, and the generated code includes a "
            "`*_self_test()` function that re-checks the same value at "
            "runtime — after your target compiler builds it."
        )


# ---------- Action sections (shared by tab bodies) ----------

def render_generate_section(
    name: str,
    entry: AlgorithmInfo | None,
    width: int,
    custom_error: str | None,
    is_custom: bool,
    key_prefix: str,
) -> None:
    """Render the code-generation controls and (on click) the output panes.

    Layout: target-language picker, implementation-variant picker (filtered
    by what the language supports at that width), function/file-basename
    text input, Generate button, then output panes per file extension when
    the user clicks Generate.

    Bumps ``bump_stats(lang)`` once on successful generation -- one tick
    per language used per click.  The output panes show the source code
    with a Download button per file; for multi-file languages (e.g. C
    emitting ``.h`` + ``.c``) the panes appear side-by-side.

    Args:
        name: Catalog algorithm name for catalog mode, or
            :data:`SENTINEL_CUSTOM` for custom mode.  Used both for crcglot
            dispatch and as the default function/file basename.
        entry: :class:`AlgorithmInfo` for custom mode; ignored in catalog
            mode (where crcglot looks ``name`` up internally).  ``None``
            triggers an error path if the user clicks Generate in custom
            mode.
        width: CRC width in bits.  Used to filter which implementation
            variants are offered (slice8 only at 32/64).
        custom_error: First validation error from the custom form, or
            ``None``.  In custom mode the Generate button is disabled while
            this is non-None.
        is_custom: Whether to dispatch through :func:`generate_custom`
            (True) or :func:`generate_catalogue` (False).
        key_prefix: Per-tab namespace for streamlit widget keys.
    """
    lang = st.segmented_control(
        "Target language",
        list(LANGUAGES),
        format_func=lang_label,
        default="c",
        key=f"{key_prefix}_lang",
    ) or "c"

    variants = available_variants(lang, int(width))

    # Help text tracks the currently-selected variant.
    _prev_variant = st.session_state.get(f"{key_prefix}_variant_picker") or variants[0]
    if _prev_variant not in variants:
        _prev_variant = variants[0]
    _, _variant_name, _variant_desc = VARIANTS[_prev_variant]

    variant = st.segmented_control(
        "Implementation",
        variants,
        format_func=variant_label,
        default=variants[0],
        key=f"{key_prefix}_variant_picker",
        help=f"{_variant_name}: {_variant_desc}",
    ) or variants[0]
    st.caption(VARIANTS[variant][2])

    sym_col, btn_col = st.columns([3, 1], vertical_alignment="bottom")
    default_sym = "custom_crc" if is_custom else default_symbol(name)

    sym_key = f"{key_prefix}_symbol"
    sym_for_key = f"{key_prefix}_symbol_for"
    if st.session_state.get(sym_for_key) != name:
        st.session_state[sym_key] = default_sym
        st.session_state[sym_for_key] = name

    with sym_col:
        symbol = st.text_input(
            "Function / file basename",
            key=sym_key,
            help="Used as the generated function name; for C, also the .c / .h basename.",
        )
    with btn_col:
        go = st.button(
            "Generate code",
            type="primary",
            disabled=(
                (not symbol.strip())
                or (is_custom and custom_error is not None)
            ),
            use_container_width=True,
            icon=":material/play_arrow:",
            key=f"{key_prefix}_go",
        )

    if go:
        try:
            if is_custom:
                result = generate_custom(lang, symbol.strip(), entry, variant, symbol.strip())
            else:
                result = generate_catalogue(lang, name, variant, symbol.strip())
        except ValueError as e:
            st.error(str(e))
            st.stop()
        if result is None:
            st.error(f"Generator returned no output for {name!r}.")
            st.stop()
        bump_stats(lang)

        with st.container(border=True):
            st.markdown(
                f'<span class="crc-section">{LANGUAGES[lang].display_name} Output</span>',
                unsafe_allow_html=True,
            )
            extensions = LANGUAGES[lang].extensions
            files = result if isinstance(result, tuple) else (result,)
            cols = st.columns(len(extensions)) if len(extensions) > 1 else (st.container(),)
            for col, ext, content in zip(cols, extensions, files):
                with col:
                    fname = f"{symbol}{ext}"
                    st.markdown(f"**\U0001F4C4 `{fname}`**  ·  *{len(content):,} bytes*")
                    st.code(content, language=lang, line_numbers=True)
                    st.download_button(
                        f"Download {ext}", content,
                        file_name=fname, mime="text/plain",
                        use_container_width=True, icon=":material/download:",
                        key=f"{key_prefix}_dl_{ext}",
                    )


def render_calculate_section(
    entry: AlgorithmInfo | None,
    custom_error: str | None,
    key_prefix: str,
    allow_verify: bool = True,
) -> None:
    """Render the Calculate(/Verify) CRC controls.

    Layout: optional test-vector checkbox, Text/Hex input-mode segmented
    control, multi-line text area, Calculate(/Verify) button.  On click,
    parses the input via :func:`parse_hex_bytes` (Hex mode) or
    ``.encode("utf-8")`` (Text mode), computes the CRC via
    :func:`_crc_compute`, bumps :data:`CALC_KEY`, and renders the result.

    When ``allow_verify=True`` and the user has the test-vector checkbox
    checked at click time, the result also shows a ✓ Match / ✗ Mismatch
    badge comparing against ``entry.check`` (the canonical reveng check
    value).  Checking the box loads ``b"123456789"`` into the input field
    in whatever representation matches the current Input format; the user
    can then edit freely -- the button always reads from the visible field.

    Args:
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

    use_test_vector = False
    if allow_verify:
        use_tv_key = f"{key_prefix}_use_tv"
        prev_tv_key = f"{key_prefix}_prev_tv"

        use_test_vector = st.checkbox(
            'Use test vector (b"123456789")',
            value=False,
            key=use_tv_key,
            help=(
                "Loads the canonical test bytes `\"123456789\"` into the "
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

    mode_col, _ = st.columns([1, 3], vertical_alignment="bottom")
    with mode_col:
        input_mode = st.segmented_control(
            "Input format",
            ["Text", "Hex"],
            default="Text",
            key=mode_state_key,
        ) or "Text"

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
        # Button label reflects what's actually about to happen: only say
        # "Verify" when verification is on (allow_verify AND test-vector
        # checkbox is checked).
        calc_go = st.button(
            "Calculate / Verify" if use_test_vector else "Calculate",
            type="primary",
            disabled=not text.strip(),
            use_container_width=True,
            icon=":material/calculate:",
            key=f"{key_prefix}_go",
        )

    if not calc_go:
        return

    if input_mode == "Hex":
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

    value = _crc_compute(
        data, entry.width, entry.poly, entry.init,
        entry.refin, entry.refout, entry.xorout,
    )
    nibbles = (entry.width + 3) // 4
    formatted = f"0x{value:0{nibbles}X}"
    bump_stats(CALC_KEY)

    with st.container(border=True):
        st.markdown('<span class="crc-section">Result</span>', unsafe_allow_html=True)
        st.markdown(
            f"**\U0001F9EE Computed CRC**  ·  `{entry.name}`  ·  "
            f'*{len(data):,} byte{"" if len(data) == 1 else "s"} input '
            f"· {entry.width}-bit*",
        )
        st.code(formatted, language=None)

        if use_test_vector:
            expected = f"0x{entry.check:0{nibbles}X}"
            ok = value == entry.check
            badge_cls = "crc-match-ok" if ok else "crc-match-fail"
            badge_text = "✓ Match" if ok else "✗ Mismatch"
            st.markdown(
                f'<span class="crc-stat-pill {badge_cls}">{badge_text}</span>'
                f'<span class="crc-match-expected">'
                f'Expected: <code>{expected}</code></span>',
                unsafe_allow_html=True,
            )
            st.caption(
                "Verification compares the computed CRC against the "
                "catalog's published **check** value — the canonical "
                "answer from Greg Cook's "
                "[reveng catalogue](https://reveng.sourceforge.io/crc-catalogue/all.htm)."
            )


# ---------- Tab bodies ----------

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
            st.markdown('<span class="crc-section">Algorithm</span>', unsafe_allow_html=True)
            _, entry, _ = render_standard_picker(key_prefix)
            custom_error = None
        else:
            st.markdown('<span class="crc-section">Parameters</span>', unsafe_allow_html=True)
            entry, _, custom_error = render_custom_picker(key_prefix)

    with st.container(border=True):
        title = "Calculate/Verify CRC" if allow_verify else "Calculate CRC"
        st.markdown(f'<span class="crc-section">{title}</span>', unsafe_allow_html=True)
        render_calculate_section(
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
            st.markdown('<span class="crc-section">Algorithm</span>', unsafe_allow_html=True)
            name, entry, width = render_standard_picker(key_prefix)
            custom_error = None
        else:
            st.markdown('<span class="crc-section">Parameters</span>', unsafe_allow_html=True)
            entry, width, custom_error = render_custom_picker(key_prefix)
            name = SENTINEL_CUSTOM
        render_test_vector_display(entry, is_custom=is_custom)

    with st.container(border=True):
        st.markdown('<span class="crc-section">Generate code</span>', unsafe_allow_html=True)
        render_generate_section(
            name=name,
            entry=entry,
            width=width,
            custom_error=custom_error,
            is_custom=is_custom,
            key_prefix=key_prefix,
        )


def render_reverse_tab() -> None:
    """Render the body of the Reverse Lookup tab.

    Has its own UI (not a composition of the picker / action helpers used by
    the other tabs) because the workflow is fundamentally different: the
    user supplies bytes + a CRC value and asks "which algorithm produced
    this?", searching the whole catalog rather than configuring one
    algorithm.

    Two modes selected via the "CRC source" segmented control:
        - **Target**: the user types the target CRC into the hex input
          field; :func:`find_matching_algorithms` searches the catalog.
        - **End-of-data** (8 / 16 / 32 / 64 bits): the last N bytes of the
          input data are treated as the trailing CRC and the rest as the
          payload; :func:`find_matching_algorithms_at_end` searches only
          algorithms of the matching width.

    In both modes the "Try big/little endian" checkbox additionally tests
    the byte-reversed interpretation of the target -- catches the common
    endianness mismatch when the CRC was captured off a byte stream in
    the opposite order from what the protocol uses on the wire.

    On click, bumps :data:`REVERSE_KEY`.  Each match renders as a green
    ✓ pill with the algorithm name; matches that hit via the reversed /
    little-endian interpretation get an additional amber ↔ pill.  The
    no-match path explains common reasons (custom polynomial, byte order,
    wrong payload bytes, not a CRC).
    """
    rev_go = False
    rev_input_mode = "Text"
    rev_text = ""
    rev_target_raw = ""

    with st.container(border=True):
        st.markdown('<span class="crc-section">Reverse Lookup</span>', unsafe_allow_html=True)
        st.caption(
            f"Have a captured payload and its trailing CRC but don't know "
            f"which algorithm produced it?  Paste both below and the "
            f"{len(ALGORITHMS)}-algorithm catalog is searched for matches.  "
            "If endianness is in doubt, enable the big/little-endian option."
        )

        mode_col, target_col = st.columns([1, 2], vertical_alignment="bottom")
        with mode_col:
            rev_input_mode = st.segmented_control(
                "Input format",
                ["Text", "Hex"],
                default="Text",
                key="rev_input_mode",
            ) or "Text"

        # CRC source selector: either the typed target value, or extract
        # the last N bytes of input data as the CRC.
        rev_source = st.segmented_control(
            "CRC source",
            ["Target", "All", "8", "16", "32", "64"],
            default="Target",
            key="rev_source",
            format_func=lambda s: (
                "Use Target" if s == "Target"
                else "Try all sizes" if s == "All"
                else f"{s}-bit at end"
            ),
            help=(
                "**Where does the CRC come from?**\n\n"
                "- **Use Target** — type the CRC value into the Target CRC "
                "field.\n"
                "- **Try all sizes** — peel a trailing CRC of every common "
                "width (8 / 16 / 32 / 64) off the input data and search "
                "them all.  Use when the CRC width is unknown.\n"
                "- **8 / 16 / 32 / 64** — same as Try all sizes but "
                "restricted to that one width.\n\n"
                "**How the trailing CRC is parsed in end-of-data modes:**\n\n"
                "- In **Text** mode, the last `N/4` hex chars are the CRC "
                "(e.g. for 16-bit, the last 4 chars `9CE1` → `0x9CE1`).  "
                "Several boundary interpretations are tried — strict, "
                "`0x` prefix peel, trailing-whitespace strip on the "
                "payload — and each match is annotated with which one hit.\n"
                "- In **Hex** mode, the input is bytes; the last `N/8` "
                "bytes are interpreted big-endian (or with opposite "
                "endianness if that checkbox is on).\n\n"
                "In all end-of-data modes, the Target CRC field is ignored."
            ),
        ) or "Target"
        try_all_sizes = rev_source == "All"
        end_of_data = rev_source not in ("Target",)
        end_width = int(rev_source) if rev_source not in ("Target", "All") else 0

        with target_col:
            rev_target_raw = st.text_input(
                "Target CRC (hex)",
                placeholder="0xcbf43926",
                disabled=end_of_data,
                help="The CRC value you're trying to match.  Up to 64 bits.",
                key="rev_target",
            )

        if try_all_sizes and rev_input_mode == "Text":
            _input_label = (
                "Input data (trailing 2 / 4 / 8 / 16 hex chars are tried as "
                "8 / 16 / 32 / 64-bit CRCs)"
            )
        elif try_all_sizes:
            _input_label = (
                "Input data (last 1 / 2 / 4 / 8 bytes are tried as "
                "8 / 16 / 32 / 64-bit CRCs)"
            )
        elif end_of_data and rev_input_mode == "Text":
            _hex_chars = end_width // 4
            _input_label = (
                f"Input data (the last {_hex_chars} chars are parsed as the "
                f"{end_width}-bit hex CRC)"
            )
        elif end_of_data:
            _n = end_width // 8
            _input_label = (
                f"Input data (the last {_n} byte"
                f"{'' if _n == 1 else 's'} are taken as the CRC)"
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

        try_endian = st.checkbox(
            "Try big/little endian",
            value=False,
            key="rev_try_endian",
            help=(
                "Catches the common endianness mismatch where the captured "
                "CRC bytes were transcribed in the opposite order from what "
                "the protocol actually uses on the wire.\n\n"
                "- In **Use Target** mode: tries the typed target as-is "
                "*and* with its bytes reversed (byte-aligned widths only — "
                "8 / 16 / 24 / 32 / 40 / 48 / 56 / 64).\n"
                "- In **end-of-data** modes (Hex): interprets the trailing "
                "bytes both as big-endian (network order, the default) and "
                "little-endian.\n"
                "- In **end-of-data** modes (Text): also tries the byte-"
                "reversed form of the parsed target integer.\n\n"
                "Matches found via the opposite interpretation are flagged "
                "with a `↔ opposite endianness` pill."
            ),
        )

        target_required = not end_of_data
        _, rev_btn_col = st.columns([3, 1], vertical_alignment="bottom")
        with rev_btn_col:
            rev_go = st.button(
                "Reverse Lookup",
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

    # Dispatch paths -- input parsing differs by mode:
    #
    #   Try all sizes (either input format): run each of 8/16/32/64 in
    #     sequence and aggregate matches.  Width annotation per result row
    #     distinguishes which width hit.
    #   Text + end-of-data: split the input string at the last 2N chars
    #     (where N = end_width // 8).  Trailing chars become a hex integer
    #     target, leading chars are the payload (UTF-8 encoded).
    #   Hex + end-of-data: hex-decode the whole input; last N bytes are the
    #     CRC interpreted as BE (and optionally LE) integer; rest is payload.
    #   Target (either input format): parse the input as bytes; target comes
    #     from the separate Target CRC field.
    target_display: str
    text_end_of_data = end_of_data and rev_input_mode == "Text" and not try_all_sizes
    hex_end_of_data = end_of_data and rev_input_mode == "Hex" and not try_all_sizes

    if try_all_sizes:
        matches = []
        with st.status(
            "Searching all common widths (8 / 16 / 32 / 64)...",
            expanded=False,
        ) as _status:
            for w in (8, 16, 32, 64):
                _status.write(f"trying {w}-bit algorithms...")
                if rev_input_mode == "Text":
                    if len(rev_text) < w // 4:
                        continue
                    partial = find_matching_algorithms_text_end(
                        rev_text, w, try_endian=try_endian,
                    )
                    matches.extend([(m[0], m[1], m[2]) for m in partial])
                else:
                    try:
                        _bytes = parse_hex_bytes(rev_text)
                    except ValueError as _e:
                        _status.write(f"hex parse failed: {_e}")
                        continue
                    if not _bytes or len(_bytes) < w // 8:
                        continue
                    partial = find_matching_algorithms_at_end(
                        _bytes, w, try_endian=try_endian,
                    )
                    matches.extend([(m[0], m[1], "") for m in partial])
            _status.update(
                label=(
                    f"Searched 8 / 16 / 32 / 64-bit widths · "
                    f"{len(matches)} match{'' if len(matches) == 1 else 'es'} found"
                ),
                state="complete",
            )
        # rev_data + target_display + input_summary for the Result header.
        if rev_input_mode == "Text":
            rev_data = rev_text.encode("utf-8")
        else:
            try:
                rev_data = parse_hex_bytes(rev_text)
            except ValueError as e:
                st.error(f"Input data: {e}")
                st.stop()
        input_summary = (
            f"{len(rev_data):,} byte input · tried widths 8 / 16 / 32 / 64"
        )
        no_match_target_display = "this input under any of widths 8 / 16 / 32 / 64"

    elif text_end_of_data:
        hex_chars = end_width // 4
        if len(rev_text) < hex_chars:
            st.error(
                f"Input has {len(rev_text)} char"
                f'{"" if len(rev_text) == 1 else "s"}; '
                f"need at least {hex_chars} trailing hex chars for a "
                f"{end_width}-bit CRC."
            )
            st.stop()
        # Multi-boundary search: tries strict, 0x-prefix-peeled, and
        # whitespace-stripped variants of the boundary.  Each match
        # carries the boundary label that produced it.
        raw_matches = find_matching_algorithms_text_end(
            rev_text, end_width, try_endian=try_endian,
        )
        # Normalize to (info, endian_annotation, boundary_label) so the
        # renderer below has one shape across all three dispatch modes.
        matches = [(m[0], m[1], m[2]) for m in raw_matches]
        nibbles = end_width // 4
        trail = rev_text[-hex_chars:]
        try:
            crc_value = int(trail, 16)
            target_display = f"0x{crc_value:0{nibbles}X}"
        except ValueError:
            target_display = f"`{trail}` (last {hex_chars} chars; not parseable as hex)"
        # Use the strict-mode payload length for the summary.  Other
        # boundary variants are tried internally but the user typically
        # cares about the literal split.
        rev_data = rev_text[:-hex_chars].encode("utf-8")
        input_summary = (
            f"{len(rev_data):,} byte text payload · {end_width}-bit trailing "
            f"hex CRC = {target_display}"
        )
        no_match_target_display = target_display

    elif hex_end_of_data:
        try:
            rev_data = parse_hex_bytes(rev_text)
        except ValueError as e:
            st.error(f"Input data: {e}")
            st.stop()
        if not rev_data:
            st.error("Input data is empty after stripping separators.")
            st.stop()
        n = end_width // 8
        if len(rev_data) < n:
            st.error(
                f"Input has {len(rev_data)} byte"
                f'{"" if len(rev_data) == 1 else "s"}; '
                f"need at least {n} for a {end_width}-bit CRC at end."
            )
            st.stop()
        raw_matches = find_matching_algorithms_at_end(
            rev_data, end_width, try_endian=try_endian,
        )
        # Normalize to (info, endian_annotation, boundary_label).
        # Hex+end-of-data has no boundary ambiguity, so the label is "".
        matches = [(m[0], m[1], "") for m in raw_matches]
        crc_bytes = rev_data[-n:]
        target_be = int.from_bytes(crc_bytes, "big")
        target_le = int.from_bytes(crc_bytes, "little")
        nibbles = end_width // 4
        if target_be == target_le:
            target_display = f"0x{target_be:0{nibbles}X}"
        else:
            target_display = (
                f"0x{target_be:0{nibbles}X} (BE) / "
                f"0x{target_le:0{nibbles}X} (LE)"
            )
        payload_len = len(rev_data) - n
        input_summary = (
            f"{payload_len:,} byte payload · {end_width}-bit trailing CRC "
            f"= {target_display}"
        )
        no_match_target_display = target_display

    else:
        # Target mode -- separate Target CRC field, full input is the payload.
        if rev_input_mode == "Hex":
            try:
                rev_data = parse_hex_bytes(rev_text)
            except ValueError as e:
                st.error(f"Input data: {e}")
                st.stop()
            if not rev_data:
                st.error("Input data is empty after stripping separators.")
                st.stop()
        else:
            rev_data = rev_text.encode("utf-8")
        target, target_err = parse_hex(rev_target_raw, "Target CRC", 64)
        if target_err:
            st.error(target_err)
            st.stop()
        assert target is not None
        raw_matches = find_matching_algorithms(
            rev_data, target, try_endian=try_endian,
        )
        # Normalize to (info, endian_annotation, boundary_label).
        # Target mode has no boundary ambiguity.
        matches = [(m[0], m[1], "") for m in raw_matches]
        target_display = f"0x{target:X}"
        input_summary = (
            f"{len(rev_data):,} byte"
            f'{"" if len(rev_data) == 1 else "s"} input · target '
            f"`{target_display}`"
        )
        no_match_target_display = f"`{target_display}`"

    bump_stats(REVERSE_KEY)

    with st.container(border=True):
        st.markdown('<span class="crc-section">Result</span>', unsafe_allow_html=True)

        if matches:
            plural = "es" if len(matches) != 1 else ""
            st.markdown(
                f"**\U0001F50D Found {len(matches)} match{plural}**  "
                f"·  *{input_summary}*"
            )
            for info, annotation, boundary_label in matches:
                badge = ""
                if annotation:
                    badge = (
                        f'<span class="crc-stat-pill crc-match-ok '
                        f'crc-annotation-pill">↔ {annotation}</span>'
                    )
                boundary_extra = (
                    f' · boundary: <em>{boundary_label}</em>'
                    if boundary_label
                    else ""
                )
                st.markdown(
                    f'<span class="crc-stat-pill crc-match-ok">'
                    f'✓ {info.name}</span>'
                    f'{badge}'
                    f'<span class="crc-match-expected">'
                    f'width {info.width}'
                    f'{boundary_extra}'
                    f'</span>',
                    unsafe_allow_html=True,
                )
                if info.desc:
                    st.caption(info.desc)
        else:
            hint = ""
            if not try_endian:
                hint = (
                    "- Try the **Try big/little endian** checkbox above "
                    "to catch endianness mismatches\n"
                )
            st.warning(
                f"No catalog algorithm produces {no_match_target_display} "
                f"for this input.\n\n"
                "Common reasons:\n"
                f"{hint}"
                "- Custom polynomial (not in the reveng catalogue)\n"
                "- Input bytes don't exactly match the captured payload "
                "(extra/missing header bytes, trailing checksum included, etc.)\n"
                "- The checksum isn't a CRC (could be Adler-32, Fletcher, "
                "truncated hash, etc.)"
            )


def render_footer() -> None:
    """Render the page footer: stats counters + build info.

    Two stacked rows:
        1. Counter totals line: ``"N generations · M calculations · K searches"``
           in orange.
        2. Pill row: one pill per crcglot language (per-language generation
           count) plus a 🧮 Calculate pill and a 🔍 Reverse pill.  Zero-count
           pills are dimmed.

    Below that, a small monospace build line: app version + git rev (linked
    to the GitHub commit) + crcglot version (linked to PyPI).
    """
    st.divider()
    stats = load_stats()
    gen_total = sum(v for k, v in stats.items() if not k.startswith("__"))
    calc_total = stats.get(CALC_KEY, 0)
    rev_total = stats.get(REVERSE_KEY, 0)

    def pill(label: str, count: int) -> str:
        zero_cls = " crc-stat-pill-zero" if count == 0 else ""
        return (
            f'<span class="crc-stat-pill{zero_cls}">'
            f'{label} <strong>{count}</strong></span>'
        )

    pills = "".join(
        pill(f"{info.emoji} {info.display_name}", stats.get(code, 0))
        for code, info in LANGUAGES.items()
    )
    pills += pill("\U0001F9EE Calculate", calc_total)
    pills += pill("\U0001F50D Reverse", rev_total)

    st.markdown(
        f'<div class="crc-stats-totals">'
        f'{gen_total} generation{"" if gen_total == 1 else "s"}'
        f' &middot; {calc_total} calculation{"" if calc_total == 1 else "s"}'
        f' &middot; {rev_total} search{"" if rev_total == 1 else "es"}'
        f'</div>'
        f'<div class="crc-stats">{pills}</div>',
        unsafe_allow_html=True,
    )

    rev = git_revision()
    rev_sha = rev[:-len("-dirty")] if rev.endswith("-dirty") else rev
    rev_link = (
        f'<a href="{REPO_URL}/commit/{rev_sha}" target="_blank">{rev}</a>'
        if rev != "unknown" else rev
    )
    crcglot_ver = crcglot_version()
    crcglot_link = (
        f'<a href="https://pypi.org/project/crcglot/{crcglot_ver}/" target="_blank">'
        f'crcglot {crcglot_ver}</a>'
        if crcglot_ver != "unknown" else f"crcglot {crcglot_ver}"
    )
    st.markdown(
        f'<div class="crc-build">'
        f'v{app_version()} &middot; rev {rev_link} &middot; {crcglot_link}'
        f'</div>',
        unsafe_allow_html=True,
    )
