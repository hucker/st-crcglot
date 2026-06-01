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
    REPO_URL,
    REVERSE_KEY,
    SENTINEL_CUSTOM,
    VARIANTS,
    alg_label,
    app_version,
    available_variants,
    bump_stats,
    catalogue_names,
    crcglot_version,
    default_symbol,
    detect_chunk,
    encode_int,
    generate_catalogue,
    generate_custom,
    generic_crc,
    git_revision,
    lang_label,
    load_stats,
    padding_pills,
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
    n = len(ALGORITHMS)
    st.markdown(
        f"""
<meta name="description" content="CRC101 -- generate and verify CRCs in your browser. Catalog of {n} algorithms, code emitters for C, Python, Rust, VHDL, C#, Go, and Zig, plus an interactive calculator.">
<meta name="keywords" content="CRC, CRC-8, CRC-16, CRC-32, CRC-64, CRC calculator, CRC code generator, cyclic redundancy check, reveng catalogue, polynomial, crcglot, C, Python, Rust, VHDL, C#, Go, Zig">
<meta name="author" content="Chuck Bass / acrocad.net">
<meta name="robots" content="index, follow">

<meta property="og:title" content="CRC101 -- CRC code generator & calculator">
<meta property="og:description" content="Generate CRC code in C, Python, Rust, VHDL, C#, Go, or Zig from {n} catalog algorithms -- or calculate a CRC over your own bytes.">
<meta property="og:type" content="website">

<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="CRC101 -- CRC code generator & calculator">
<meta name="twitter:description" content="Generate CRC code in C, Python, Rust, VHDL, C#, Go, or Zig from {n} catalog algorithms -- or calculate a CRC over your own bytes.">
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
    )
    if entry.desc:
        st.caption(f"_{entry.desc}_")

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

    nibbles = (entry.width + 3) // 4
    # Custom path: compute live from the user's typed parameters (no
    # registered name to defer to).  Catalog path: entry.check IS the
    # test-vector CRC by definition -- no compute, just display it.
    if is_custom:
        value = generic_crc(
            b"123456789", entry.width, entry.poly, entry.init,
            entry.refin, entry.refout, entry.xorout,
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
                    "The CRC of `b\"123456789\"` computed live from "
                    "your custom parameters."
                ),
            )
            if ok:
                st.badge(
                    "matches Check",
                    color="green",
                    icon=":material/check:",
                    help=f"Equals the **Check** value you typed: `{expected}`.",
                )
            else:
                st.badge(
                    "mismatch with typed Check",
                    color="red",
                    icon=":material/close:",
                    help=(
                        f"Differs from the **Check** value you typed: "
                        f"`{expected}`.  Either the parameters or the "
                        f"Check field needs adjusting."
                    ),
                )
        st.caption(
            "Computed live from your parameters by `crcglot`.  The ✓/✗ "
            "badge compares it to the **Check** value you typed; if it "
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
                "algorithm -- the CRC of `b\"123456789\"`."
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
    st.caption(
        f"{VARIANTS[variant][2]}  "
        "Speed-up figures are rough — see "
        "[crcglot's BENCHMARKS.md]"
        "(https://github.com/hucker/crcglot/blob/main/BENCHMARKS.md) "
        "for measured numbers."
    )

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
            st.subheader(f"View {LANGUAGES[lang].display_name} Output")
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

    # Defer to crcglot: catalog algorithms compute via encode_int(name);
    # custom algorithms have no registered name so we hand crcglot the
    # raw parameter tuple from the user's typed AlgorithmInfo.
    if entry.name in ALGORITHMS:
        value = encode_int(data, entry.name)
    else:
        value = generic_crc(
            data, entry.width, entry.poly, entry.init,
            entry.refin, entry.refout, entry.xorout,
        )
    nibbles = (entry.width + 3) // 4
    formatted = f"0x{value:0{nibbles}X}"
    bump_stats(CALC_KEY)

    with st.container(border=True):
        st.subheader("View Result")
        st.markdown(
            f"**\U0001F9EE Computed CRC**  ·  `{entry.name}`  ·  "
            f'*{len(data):,} byte{"" if len(data) == 1 else "s"} input '
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
    with st.container(border=True):
        st.markdown(
            f"""
{ack_block}### What CRC101 does

- **Generate CRC code** in C, C#, Go, Python, Rust, TypeScript,
  Verilog, or VHDL — for any of {len(ALGORITHMS)} catalog algorithms or a custom
  polynomial you define.
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
            _, entry, _ = render_standard_picker(key_prefix)
            custom_error = None
        else:
            st.subheader("Select Parameters")
            entry, _, custom_error = render_custom_picker(key_prefix)

    with st.container(border=True):
        title = "Calculate/Verify CRC" if allow_verify else "Calculate CRC"
        st.subheader(title)
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
            st.subheader("Select Algorithm")
            name, entry, width = render_standard_picker(key_prefix)
            custom_error = None
        else:
            st.subheader("Select Parameters")
            entry, width, custom_error = render_custom_picker(key_prefix)
            name = SENTINEL_CUSTOM
        render_test_vector_display(entry, is_custom=is_custom)

    with st.container(border=True):
        st.subheader("Generate code")
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
        st.subheader("Reverse Lookup")
        st.caption(
            f"Have a captured payload and its trailing CRC but don't know "
            f"which algorithm produced it?  Paste both below and the "
            f"{len(ALGORITHMS)}-algorithm catalog is searched for matches.  "
            "Endianness, `0x` prefixes, uppercase hex, and separators are "
            "handled automatically by crcglot's `detect()`."
        )

        mode_col, _ = st.columns([1, 2], vertical_alignment="bottom")
        with mode_col:
            rev_input_mode = st.segmented_control(
                "Input format",
                ["Text", "Hex"],
                default="Text",
                key="rev_input_mode",
            ) or "Text"

        # CRC source: either treat the trailing bytes/chars of the input
        # as the CRC and let detect() find the boundary (Any / per-width),
        # or supply the target value separately (Target -- last in the
        # list since detect() handles the common cases).
        rev_source = st.segmented_control(
            "CRC source",
            ["Any", "8", "16", "32", "64", "Target"],
            default="Any",
            key="rev_source",
            format_func=lambda s: (
                "Use Target" if s == "Target"
                else "Detect (any width)" if s == "Any"
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
        ) or "Any"
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
                rev_text, width=end_width or None, mode=detect_mode,
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
                rev_text, mode=detect_mode, target_crc=target,
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
                f"**\U0001F50D Found {len(matches)} match{plural}**  "
                f"·  *{input_summary}*"
            )
            for info, endian, padding in matches:
                # Row 1: the green algorithm-name badge (the "we found
                # it" anchor for this match).
                st.badge(
                    info.name,
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

    st.caption(
        f"**{gen_total} generation{'' if gen_total == 1 else 's'}**"
        f" · **{calc_total} calculation{'' if calc_total == 1 else 's'}**"
        f" · **{rev_total} search{'' if rev_total == 1 else 'es'}**"
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
            f"\U0001F9EE Calculate: {calc_total}",
            color="gray",
            help="Number of times someone clicked **Calculate** in either Calc tab.",
        )
        st.badge(
            f"\U0001F50D Reverse: {rev_total}",
            color="gray",
            help="Number of times someone clicked **Reverse Lookup**.",
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
