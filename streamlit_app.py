"""CRC101 -- generate and verify CRCs in the browser, powered by crcglot."""
from __future__ import annotations

import json
import re
import subprocess
import tomllib
from dataclasses import asdict
from importlib.metadata import PackageNotFoundError, version as pkg_version
from pathlib import Path

import streamlit as st
from crcglot import ALGORITHMS, LANGUAGES, AlgorithmInfo, generic_crc as _crc_compute

REPO_URL = "https://github.com/hucker/st-crcglot"
APP_ROOT = Path(__file__).resolve().parent


@st.cache_data
def app_version() -> str:
    try:
        data = tomllib.loads((APP_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        return data["project"]["version"]
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return "unknown"


@st.cache_data
def crcglot_version() -> str:
    try:
        return pkg_version("crcglot")
    except PackageNotFoundError:
        return "unknown"


def git_revision() -> str:
    """Short SHA + ``-dirty`` suffix; ``unknown`` if git isn't available.

    Not cached -- a streamlit-watch reload after a commit shows the new SHA
    without having to restart the server.  ``git describe`` is sub-50ms.
    """
    try:
        out = subprocess.check_output(
            ["git", "describe", "--tags", "--always", "--dirty"],
            cwd=APP_ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return out or "unknown"
    except (OSError, subprocess.CalledProcessError):
        return "unknown"

STATS_FILE = Path(__file__).resolve().parent / "crcglot_stats.json"


def load_stats() -> dict[str, int]:
    try:
        raw = json.loads(STATS_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return {k: int(v) for k, v in raw.items() if isinstance(v, (int, float))}


CALC_KEY = "__calculate__"  # not a language code -- excluded from per-lang pills.
REVERSE_KEY = "__reverse__"  # ditto -- reverse-lookup tab counter.


def find_matching_algorithms(data: bytes, target: int) -> list[AlgorithmInfo]:
    """Return every catalogue entry whose CRC of ``data`` equals ``target``."""
    matches: list[AlgorithmInfo] = []
    for info in ALGORITHMS.values():
        # Skip widths that can't represent ``target`` at all.
        if target > ((1 << info.width) - 1):
            continue
        value = _crc_compute(
            data, info.width, info.poly, info.init,
            info.refin, info.refout, info.xorout,
        )
        if value == target:
            matches.append(info)
    return matches


def render_standard_picker(key_prefix: str) -> tuple[str, AlgorithmInfo, int]:
    """Render the catalogue selectbox + parameter metrics card.

    Always returns a valid algorithm; defaults to ``crc32`` on first call.
    """
    state_key = f"{key_prefix}_last_catalogue"
    if state_key not in st.session_state:
        st.session_state[state_key] = "crc32"

    name = st.selectbox(
        "CRC algorithm",
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

    st.divider()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Width",      f"{entry.width} bits")
    m2.metric("Polynomial", hex(entry.poly))
    m3.metric("Init",       hex(entry.init))
    m4.metric("Check",      hex(entry.check))
    with st.expander("All parameters (reflect / xorout / description)"):
        st.json({
            k: (hex(v) if isinstance(v, int) and k != "width" else v)
            for k, v in asdict(entry).items()
        })

    return name, entry, entry.width


def render_custom_picker(
    key_prefix: str,
) -> tuple[AlgorithmInfo | None, int, str | None]:
    """Render the 4x2 custom-parameter form.

    Returns ``(entry, width, custom_error)``.  ``entry`` is None when any
    field fails validation; ``custom_error`` then carries the first error.
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
                "Polynomial (hex)", value=hex(seed.poly),
                key=f"{key_prefix}_poly",
            )
        with r1c4:
            init_raw = st.text_input(
                "Init (hex)", value=hex(seed.init),
                key=f"{key_prefix}_init",
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
                value=hex(seed.check),
                key=f"{key_prefix}_check",
                help='CRC of the ASCII bytes "123456789". Used by the generated self-test.',
            )
        with r2c3:
            xorout_raw = st.text_input(
                "Xorout (hex)", value=hex(seed.xorout),
                key=f"{key_prefix}_xorout",
            )
        with r2c4:
            st.markdown(
                '<div class="crc-grid-empty"></div>', unsafe_allow_html=True,
            )

    desc = st.text_input(
        "Description",
        value="custom",
        key=f"{key_prefix}_desc",
        help="Update this to be the name of the function called in the target code.",
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


def render_generate_section(
    name: str,
    entry: AlgorithmInfo | None,
    width: int,
    custom_error: str | None,
    is_custom: bool,
    key_prefix: str,
) -> None:
    """Render the language picker, variant picker, symbol input, Generate
    button, and (on click) the output panes.  Used by both the Standard
    and Custom tabs.
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
    """Render Calculate(/Verify) CRC controls: text/hex input, button, and
    (on click) the result.  When ``allow_verify`` is True (Standard tab),
    also shows a test-vector checkbox that loads ``b"123456789"`` into the
    input and renders a match badge against ``entry.check``.  When False
    (Custom tab), verification is suppressed because the user's typed
    check value isn't an authoritative source of truth.

    If ``entry`` is None (custom form has errors), shows a helpful info
    banner instead and skips the inputs.
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
            help="Loads the canonical test bytes into the input below.  When "
                 "checked, the result is compared against the catalogue's "
                 "check value.",
        )

        # On unchecked -> checked transition, copy the test vector into the
        # input field in whatever representation matches the current mode --
        # Text mode gets "123456789", Hex mode gets the byte pairs.  The
        # Calculate button always reads from the visible input below, so what
        # the user sees is what gets CRC'd.
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
            "Hex mode strips 0x/0X prefixes, ':', ',' and whitespace, "
            "then consumes the rest as two-nibble byte pairs."
        ),
        key=text_state_key,
    )

    _, btn_col = st.columns([3, 1], vertical_alignment="bottom")
    with btn_col:
        calc_go = st.button(
            "Calculate/Verify" if allow_verify else "Calculate",
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
    formatted = f"0x{value:0{nibbles}x}"
    bump_stats(CALC_KEY)

    with st.container(border=True):
        st.markdown('<span class="crc-section">Result</span>', unsafe_allow_html=True)
        st.markdown(
            f"**\U0001F9EE Computed CRC**  ·  *{len(data):,} byte"
            f'{"" if len(data) == 1 else "s"} input · {entry.width}-bit*',
        )
        st.code(formatted, language=None)

        # Verify against the catalogue / user-configured check value whenever
        # the test-vector checkbox is on at click time.  This stays informative
        # even if the user edits the input away from "123456789" -- a mismatch
        # then tells them "you changed the input but verification is still on."
        if use_test_vector:
            expected = f"0x{entry.check:0{nibbles}x}"
            ok = value == entry.check
            badge_cls = "crc-match-ok" if ok else "crc-match-fail"
            badge_text = "✓ Match" if ok else "✗ Mismatch"
            st.markdown(
                f'<span class="crc-stat-pill {badge_cls}">{badge_text}</span>'
                f'<span class="crc-match-expected">'
                f'Expected: <code>{expected}</code></span>',
                unsafe_allow_html=True,
            )


def bump_stats(key: str) -> dict[str, int]:
    stats = load_stats()
    stats[key] = stats.get(key, 0) + 1
    tmp = STATS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(stats), encoding="utf-8")
    tmp.replace(STATS_FILE)
    return stats

VARIANTS: dict[str, tuple[str, str, str]] = {
    "bitwise": ("◯", "Bit-by-bit",   "Smallest; portable; one byte per 8 shifts."),
    "table":   ("▦", "Table-driven", "256-entry LUT; 4-8x faster than bit-by-bit."),
    "slice8":  ("▩", "Slice-by-8",   "8 LUTs; another 5-10x faster (32/64-bit CRCs only)."),
}

VARIANT_ORDER: tuple[str, ...] = ("bitwise", "table", "slice8")

SENTINEL_CUSTOM = "__custom__"


def available_variants(code: str, width: int) -> list[str]:
    supported = LANGUAGES[code].variants
    return [
        v for v in VARIANT_ORDER
        if v in supported and not (v == "slice8" and width not in (32, 64))
    ]


def _kwargs_for_variant(variant: str) -> dict:
    if variant == "table":
        return {"table": True}
    if variant == "slice8":
        return {"slice8": True}
    return {}


def generate_catalogue(lang: str, name: str, variant: str, symbol: str):
    return LANGUAGES[lang].generator(
        name, symbol=symbol or None, **_kwargs_for_variant(variant),
    )


def generate_custom(lang: str, name: str, entry: AlgorithmInfo, variant: str, symbol: str):
    return LANGUAGES[lang].generator_from_entry(
        name, entry, symbol=symbol or None, **_kwargs_for_variant(variant),
    )


def default_symbol(name: str) -> str:
    return name.replace("-", "_")


def alg_label(name: str) -> str:
    w = ALGORITHMS[name].width
    return f"CRC-{w:<2}  ·  {name}"


def lang_label(k: str) -> str:
    info = LANGUAGES[k]
    return f"{info.emoji}  {info.display_name}"


def variant_label(v: str) -> str:
    icon, name, _ = VARIANTS[v]
    return f"{icon}  {name}"


def parse_hex(raw: str, label: str, width: int) -> tuple[int | None, str | None]:
    """Return (value, error_msg).  None error means OK."""
    s = raw.strip()
    if not s:
        return None, f"{label} is required."
    try:
        v = int(s, 16)
    except ValueError:
        return None, f"{label}: {s!r} is not a valid hex integer."
    if v < 0:
        return None, f"{label} must be non-negative."
    mask = (1 << width) - 1
    if v & ~mask:
        return None, f"{label}: 0x{v:X} exceeds width = {width} bits (max 0x{mask:X})."
    return v, None


_HEX_STRIP_RE = re.compile(r"0x|0X|[:,\s]")


def parse_hex_bytes(s: str) -> bytes:
    """Parse a hex dump into bytes.

    Strips ``0x`` / ``0X`` prefixes, ``:``, ``,``, and whitespace, then
    consumes the remainder in two-nibble pairs.  Raises ``ValueError`` with
    a UI-friendly message on bad input.
    """
    cleaned = _HEX_STRIP_RE.sub("", s)
    if not cleaned:
        return b""
    if not re.fullmatch(r"[0-9a-fA-F]+", cleaned):
        bad = next(c for c in cleaned if c not in "0123456789abcdefABCDEF")
        raise ValueError(f"Non-hex character {bad!r} in input after stripping.")
    if len(cleaned) % 2:
        raise ValueError(f"Hex input has an odd number of nibbles ({len(cleaned)}).")
    return bytes.fromhex(cleaned)


st.set_page_config(
    page_title="CRC101",
    page_icon="🛡️",
    layout="wide",
)

# SEO meta block.  Streamlit doesn't expose a way to write into <head>, so
# these tags land in <body>.  Modern Google (which JS-renders) picks them up;
# strict / non-JS crawlers won't.  Drop a reverse-proxy in front for a real
# fix.  No canonical URL yet -- add og:url and <link rel=canonical> when the
# deploy URL is known.
st.markdown(
    """
<meta name="description" content="CRC101 -- generate and verify CRCs in your browser. Catalogue of 70+ algorithms, code emitters for C, Python, Rust, VHDL, C#, Go, and Zig, plus an interactive calculator.">
<meta name="keywords" content="CRC, CRC-8, CRC-16, CRC-32, CRC-64, CRC calculator, CRC code generator, cyclic redundancy check, reveng catalogue, polynomial, crcglot, C, Python, Rust, VHDL, C#, Go, Zig">
<meta name="author" content="Chuck Bass / acrocad.net">
<meta name="robots" content="index, follow">

<meta property="og:title" content="CRC101 -- CRC code generator & calculator">
<meta property="og:description" content="Generate CRC code in C, Python, Rust, VHDL, C#, Go, or Zig from 70+ catalogue algorithms -- or calculate a CRC over your own bytes.">
<meta property="og:type" content="website">

<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="CRC101 -- CRC code generator & calculator">
<meta name="twitter:description" content="Generate CRC code in C, Python, Rust, VHDL, C#, Go, or Zig from 70+ catalogue algorithms -- or calculate a CRC over your own bytes.">
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
<style>
    .block-container { padding-top: 2rem; }

    [data-testid="stCodeBlock"] {
        border-radius: 10px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
        overflow: hidden;
    }

    /* Metric tiles -- bordered cards so the four parameter cells
       group visually on wide screens instead of drifting in white. */
    [data-testid="stMetric"] {
        background: #FAFAFA;
        border: 1px solid #E5E7EB;
        border-radius: 10px;
        padding: 0.75rem 1rem;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
        transition: border-color 0.15s ease-in-out;
    }
    [data-testid="stMetric"]:hover {
        border-color: #FF6B35;
    }
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

    /* Monospace any text input whose label ends with "(hex)" --
       Polynomial / Init / Check / Xorout in the custom-algorithm row. */
    [data-testid="stTextInput"] input[aria-label$="(hex)"] {
        font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', monospace;
        font-size: 0.95rem;
        letter-spacing: 0.02em;
    }

    /* Custom-algorithm 4x2 input grid -- bordered cells matching the
       metric tile look so the parameter region feels like a grid, not
       floating widgets.  Empty cell (marked with .crc-grid-empty) opts
       out so the bottom-right slot doesn't render as a phantom box. */
    /* Match any st.container(key="...custom-grid") regardless of tab prefix
       (gen_custom-grid, calc_custom-grid). */
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

    /* Per-language usage-counter pill row at the bottom of the page. */
    .crc-stats {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 0.4rem;
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

    /* Calculate-tab verdict badges -- same pill geometry as .crc-stat-pill
       but recolored to read as success / failure at a glance. */
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
        font-size: 2.1rem;
    }
    .crc-hero h1 .crc-hero-101 {
        color: #FF6B35;
    }
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
    .crc-hero { padding-bottom: 1.2rem; }

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

st.markdown(
    """
<div class="crc-hero">
  <h1>🛡️ CRC<span class="crc-hero-101">101</span></h1>
  <p class="crc-subtitle">
    Generate CRC code &middot; calculate CRCs &middot; catalogue from
    <a href="https://reveng.sourceforge.io/crc-catalogue/all.htm" target="_blank">reveng</a>
    &middot; powered by
    <a href="https://github.com/hucker/crcglot" target="_blank">crcglot</a>
    &middot; <a href="https://pypi.org/project/crcglot/" target="_blank">PyPI</a>
  </p>
</div>
    """,
    unsafe_allow_html=True,
)

# Width ascending, then name ascending: groups crc8 -> 16 -> 32 -> 64 in the picker.
catalogue_names = sorted(
    ALGORITHMS, key=lambda n: (ALGORITHMS[n].width, n),
)

tab_standard, tab_custom, tab_reverse = st.tabs(
    ["📚 Standard Algorithms", "✏️ Custom Algorithm", "🔍 Reverse Lookup"]
)

with tab_standard:
    with st.container(border=True):
        st.markdown('<span class="crc-section">Algorithm</span>', unsafe_allow_html=True)
        std_name, std_entry, std_width = render_standard_picker("std")

    with st.container(border=True):
        st.markdown('<span class="crc-section">Generate code</span>', unsafe_allow_html=True)
        render_generate_section(
            name=std_name,
            entry=std_entry,
            width=std_width,
            custom_error=None,
            is_custom=False,
            key_prefix="std",
        )

    with st.container(border=True):
        st.markdown(
            '<span class="crc-section">Calculate/Verify CRC</span>',
            unsafe_allow_html=True,
        )
        render_calculate_section(
            entry=std_entry,
            custom_error=None,
            key_prefix="std_calc",
        )

with tab_custom:
    with st.container(border=True):
        st.markdown('<span class="crc-section">Parameters</span>', unsafe_allow_html=True)
        cust_entry, cust_width, cust_error = render_custom_picker("cust")

    with st.container(border=True):
        st.markdown('<span class="crc-section">Generate code</span>', unsafe_allow_html=True)
        render_generate_section(
            name=SENTINEL_CUSTOM,
            entry=cust_entry,
            width=cust_width,
            custom_error=cust_error,
            is_custom=True,
            key_prefix="cust",
        )

    with st.container(border=True):
        st.markdown(
            '<span class="crc-section">Calculate CRC</span>',
            unsafe_allow_html=True,
        )
        render_calculate_section(
            entry=cust_entry,
            custom_error=cust_error,
            key_prefix="cust_calc",
            allow_verify=False,
        )

with tab_reverse:
    rev_go = False
    rev_input_mode = "Text"
    rev_text = ""
    rev_target_raw = ""

    with st.container(border=True):
        st.markdown('<span class="crc-section">Reverse</span>', unsafe_allow_html=True)
        st.caption(
            f"Given known input bytes and the resulting CRC, search the "
            f"{len(ALGORITHMS)}-algorithm catalogue for any matches.  "
            "The algorithm picker above is ignored on this tab."
        )

        mode_col, target_col = st.columns([1, 2], vertical_alignment="bottom")
        with mode_col:
            rev_input_mode = st.segmented_control(
                "Input format",
                ["Text", "Hex"],
                default="Text",
                key="rev_input_mode",
            ) or "Text"
        with target_col:
            rev_target_raw = st.text_input(
                "Target CRC (hex)",
                placeholder="0xcbf43926",
                help="The CRC value you're trying to match.  Up to 64 bits.",
                key="rev_target",
            )

        rev_text = st.text_area(
            "Input data (bytes that produced the CRC)",
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

        _, rev_btn_col = st.columns([3, 1], vertical_alignment="bottom")
        with rev_btn_col:
            rev_go = st.button(
                "Reverse Lookup",
                type="primary",
                disabled=(not rev_text.strip() or not rev_target_raw.strip()),
                use_container_width=True,
                icon=":material/search:",
            )

    if rev_go:
        # Parse input bytes
        if rev_input_mode == "Hex":
            try:
                rev_data: bytes | None = parse_hex_bytes(rev_text)
            except ValueError as e:
                st.error(f"Input data: {e}")
                st.stop()
            if not rev_data:
                st.error("Input data is empty after stripping separators.")
                st.stop()
        else:
            rev_data = rev_text.encode("utf-8")

        # Parse target CRC (validate at the 64-bit ceiling -- per-algorithm
        # width check happens inside find_matching_algorithms).
        target, target_err = parse_hex(rev_target_raw, "Target CRC", 64)
        if target_err:
            st.error(target_err)
            st.stop()
        assert target is not None  # narrowing: parse_hex returns int when err is None

        matches = find_matching_algorithms(rev_data, target)
        bump_stats(REVERSE_KEY)

        with st.container(border=True):
            st.markdown('<span class="crc-section">Result</span>', unsafe_allow_html=True)
            target_display = f"0x{target:x}"

            if matches:
                plural = "es" if len(matches) != 1 else ""
                st.markdown(
                    f"**\U0001F50D Found {len(matches)} match{plural}**  "
                    f"·  *{len(rev_data):,} byte"
                    f'{"" if len(rev_data) == 1 else "s"} input · target '
                    f"`{target_display}`*"
                )
                for info in matches:
                    nibbles = (info.width + 3) // 4
                    poly_hex = f"0x{info.poly:0{nibbles}x}"
                    st.markdown(
                        f'<span class="crc-stat-pill crc-match-ok">'
                        f'✓ {info.name}</span>'
                        f'<span class="crc-match-expected">'
                        f'width {info.width} · poly <code>{poly_hex}</code>'
                        f'</span>',
                        unsafe_allow_html=True,
                    )
                    if info.desc:
                        st.caption(info.desc)
            else:
                st.warning(
                    f"No catalogue algorithm produces `{target_display}` for "
                    f"this {len(rev_data):,}-byte input.\n\n"
                    "Common reasons:\n"
                    "- Custom polynomial (not in the reveng catalogue)\n"
                    "- CRC bytes in different byte order (try swapping endianness)\n"
                    "- Input bytes don't exactly match the captured payload "
                    "(extra/missing header bytes, trailing checksum included, etc.)\n"
                    "- The checksum isn't a CRC (could be Adler-32, Fletcher, "
                    "truncated hash, etc.)"
                )

# ---------- Usage counter (always rendered) ----------
st.divider()
_stats = load_stats()
_gen_total = sum(v for k, v in _stats.items() if not k.startswith("__"))
_calc_total = _stats.get(CALC_KEY, 0)
_rev_total = _stats.get(REVERSE_KEY, 0)


def _pill(label: str, count: int) -> str:
    zero_cls = " crc-stat-pill-zero" if count == 0 else ""
    return (
        f'<span class="crc-stat-pill{zero_cls}">'
        f'{label} <strong>{count}</strong></span>'
    )


def _lang_pill(code: str) -> str:
    info = LANGUAGES[code]
    return _pill(f"{info.emoji} {info.display_name}", _stats.get(code, 0))


_pills = "".join(_lang_pill(code) for code in LANGUAGES)
_pills += _pill("\U0001F9EE Calculate", _calc_total)
_pills += _pill("\U0001F50D Reverse", _rev_total)
st.markdown(
    f'<div class="crc-stats">'
    f'<span class="crc-stats-total">'
    f'{_gen_total} generation{"" if _gen_total == 1 else "s"}'
    f' &middot; {_calc_total} calculation{"" if _calc_total == 1 else "s"}'
    f' &middot; {_rev_total} search{"" if _rev_total == 1 else "es"}'
    f'</span>'
    f'{_pills}'
    f'</div>',
    unsafe_allow_html=True,
)

_rev = git_revision()
_rev_sha = _rev[:-len("-dirty")] if _rev.endswith("-dirty") else _rev
_rev_link = (
    f'<a href="{REPO_URL}/commit/{_rev_sha}" target="_blank">{_rev}</a>'
    if _rev != "unknown"
    else _rev
)
_crcglot_ver = crcglot_version()
_crcglot_link = (
    f'<a href="https://pypi.org/project/crcglot/{_crcglot_ver}/" target="_blank">'
    f'crcglot {_crcglot_ver}</a>'
    if _crcglot_ver != "unknown"
    else f"crcglot {_crcglot_ver}"
)
st.markdown(
    f'<div class="crc-build">'
    f'v{app_version()} &middot; rev {_rev_link} &middot; {_crcglot_link}'
    f'</div>',
    unsafe_allow_html=True,
)
