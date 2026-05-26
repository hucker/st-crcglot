"""Streamlit UI for crcglot -- generate CRC code in any language crcglot ships."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import streamlit as st
from crcglot import ALGORITHMS, LANGUAGES, AlgorithmInfo

STATS_FILE = Path(__file__).resolve().parent / "crcglot_stats.json"


def load_stats() -> dict[str, int]:
    try:
        raw = json.loads(STATS_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return {k: int(v) for k, v in raw.items() if isinstance(v, (int, float))}


def bump_stats(lang: str) -> dict[str, int]:
    stats = load_stats()
    stats[lang] = stats.get(lang, 0) + 1
    tmp = STATS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(stats), encoding="utf-8")
    tmp.replace(STATS_FILE)
    return stats

# UI presentation only.  crcglot itself ships behavioral metadata
# (extensions, variants, callables) but no icons or display names --
# those are pure UI choices and live here.  Unknown keys fall back to
# a neutral icon so a freshly-shipped crcglot language renders cleanly
# until we add its icon.
LANG_DISPLAY: dict[str, tuple[str, str]] = {  # code -> (icon, display)
    "c":      ("⚙️", "C / C++"),
    "csharp": ("\U0001F4A0", "C#"),
    "go":     ("\U0001F6A6", "Go"),
    "python": ("\U0001F40D", "Python"),
    "rust":   ("\U0001F980", "Rust"),
    "vhdl":   ("\U0001F50C", "VHDL"),
    "zig":    ("⚡", "Zig"),
}


def lang_display(code: str) -> tuple[str, str]:
    return LANG_DISPLAY.get(code, ("\U0001F4E6", code))


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
    if name == SENTINEL_CUSTOM:
        return "✏️  Custom — enter your own parameters"
    w = ALGORITHMS[name].width
    return f"CRC-{w:<2}  ·  {name}"


def lang_label(k: str) -> str:
    icon, name = lang_display(k)
    return f"{icon}  {name}"


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


st.set_page_config(
    page_title="CRC Function Generator",
    page_icon="🛡️",
    layout="wide",
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
    .st-key-custom-grid [data-testid="stColumn"] {
        background: #FAFAFA;
        border: 1px solid #E5E7EB;
        border-radius: 10px;
        padding: 0.6rem 0.85rem;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
    }
    .st-key-custom-grid [data-testid="stColumn"]:has(.crc-grid-empty) {
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
</style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="crc-hero">
  <h1>🛡️ CRC Function Generator</h1>
  <p class="crc-subtitle">
    Powered by <a href="https://github.com/hucker/crcglot" target="_blank">crcglot</a>
    &middot; <a href="https://pypi.org/project/crcglot/" target="_blank">PyPI</a>
  </p>
</div>
    """,
    unsafe_allow_html=True,
)

# Sort: width ascending, then name ascending.  Groups crc8 -> 16 -> 32 -> 64.
# Custom sentinel pinned to the top.
catalogue_names = sorted(
    ALGORITHMS, key=lambda n: (ALGORITHMS[n].width, n),
)
names = [SENTINEL_CUSTOM] + catalogue_names

if "last_catalogue_name" not in st.session_state:
    st.session_state.last_catalogue_name = "crc32"

with st.container(border=True):
    st.markdown('<span class="crc-section">Configure</span>', unsafe_allow_html=True)

    name = st.selectbox(
        "CRC algorithm",
        names,
        format_func=alg_label,
        index=names.index("crc32"),
        help=f"{len(catalogue_names)} named algorithms from the reveng catalogue plus a custom option.",
    )

    is_custom = name == SENTINEL_CUSTOM

    if not is_custom:
        st.session_state.last_catalogue_name = name
        width = ALGORITHMS[name].width
        custom_error: str | None = None
    else:
        seed = ALGORITHMS[st.session_state.last_catalogue_name]
        st.caption(
            f"Editing custom parameters — seeded from "
            f"`{st.session_state.last_catalogue_name}`. "
            "All hex fields accept `0x...` or bare hex (e.g. `1021`)."
        )

    lang = st.segmented_control(
        "Target language",
        list(LANGUAGES),
        format_func=lang_label,
        default="c",
    ) or "c"

    if is_custom:
        # 4-column x 2-row grid so every cell has the same width.
        # Row 1: Refin   | Width | Polynomial | Init
        # Row 2: Refout  | Check | Xorout     | (empty)
        with st.container(key="custom-grid"):
            r1c1, r1c2, r1c3, r1c4 = st.columns(4, vertical_alignment="bottom")
            with r1c1:
                refin = st.checkbox("Reflect input (refin)", value=seed.refin)
            with r1c2:
                width = st.number_input(
                    "Width (bits)",
                    min_value=1, max_value=64,
                    value=int(seed.width),
                    step=1,
                    help="CRC register width, 1-64 bits.",
                )
            with r1c3:
                poly_raw = st.text_input("Polynomial (hex)", value=hex(seed.poly))
            with r1c4:
                init_raw = st.text_input("Init (hex)", value=hex(seed.init))

            r2c1, r2c2, r2c3, r2c4 = st.columns(4, vertical_alignment="bottom")
            with r2c1:
                refout = st.checkbox("Reflect output (refout)", value=seed.refout)
            with r2c2:
                check_raw = st.text_input(
                    "Check (hex)",
                    value=hex(seed.check),
                    help='CRC of the ASCII bytes "123456789". Used by the generated self-test.',
                )
            with r2c3:
                xorout_raw = st.text_input("Xorout (hex)", value=hex(seed.xorout))
            with r2c4:
                st.markdown(
                    '<div class="crc-grid-empty"></div>',
                    unsafe_allow_html=True,
                )

        desc = st.text_input(
            "Description",
            value="custom",
            help="Update this to be the name of the function called in the target code.",
        )

        # Validate every hex field; collect first error.
        custom_error = None
        poly,   e1 = parse_hex(poly_raw,   "Polynomial", int(width))
        init,   e2 = parse_hex(init_raw,   "Init",       int(width))
        check,  e3 = parse_hex(check_raw,  "Check",      int(width))
        xorout, e4 = parse_hex(xorout_raw, "Xorout",     int(width))
        for err in (e1, e2, e3, e4):
            if err and not custom_error:
                custom_error = err

        entry: AlgorithmInfo | None
        if custom_error:
            st.error(custom_error)
            entry = None
        else:
            entry = AlgorithmInfo(
                name=desc or "custom", width=int(width),
                poly=poly, init=init,
                refin=refin, refout=refout,
                xorout=xorout, check=check, desc=desc,
            )

    variants = available_variants(lang, int(width))
    variant = st.segmented_control(
        "Implementation",
        variants,
        format_func=variant_label,
        default=variants[0],
        help=(
            "VHDL only emits bit-by-bit."
            if lang == "vhdl"
            else "Slice-by-8 trades code size for throughput."
            if "slice8" in variants
            else f"Slice-by-8 is only available for C / Rust at width 32 or 64 (this CRC is width {width})."
        ),
    ) or variants[0]

    st.caption(VARIANTS[variant][2])

    if not is_custom:
        cat = ALGORITHMS[name]
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Width",      f"{cat.width} bits")
        m2.metric("Polynomial", hex(cat.poly))
        m3.metric("Init",       hex(cat.init))
        m4.metric("Check",      hex(cat.check))

        with st.expander("All parameters (reflect / xorout / description)"):
            st.json({
                k: (hex(v) if isinstance(v, int) and k != "width" else v)
                for k, v in asdict(cat).items()
            })

with st.container(border=True):
    st.markdown('<span class="crc-section">Generate</span>', unsafe_allow_html=True)

    sym_col, btn_col = st.columns([3, 1], vertical_alignment="bottom")
    default_sym = "custom_crc" if is_custom else default_symbol(name)
    with sym_col:
        symbol = st.text_input(
            "Function / file basename",
            value=default_sym,
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
        st.markdown('<span class="crc-section">Output</span>', unsafe_allow_html=True)

        # Multi-file languages (today: C with .h/.c) return a tuple; single-
        # file languages return a string.  Normalize and render one pane per
        # extension declared by crcglot.
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
                )

# ---------- Usage counter (always rendered) ----------
st.divider()
_stats = load_stats()
_total = sum(_stats.values())
def _stat_pill(code: str) -> str:
    icon, name = lang_display(code)
    count = _stats.get(code, 0)
    zero_cls = " crc-stat-pill-zero" if count == 0 else ""
    return (
        f'<span class="crc-stat-pill{zero_cls}">'
        f'{icon} {name} <strong>{count}</strong></span>'
    )

_pills = "".join(_stat_pill(code) for code in LANGUAGES)
st.markdown(
    f'<div class="crc-stats">'
    f'<span class="crc-stats-total">{_total} generation{"" if _total == 1 else "s"}</span>'
    f'{_pills}'
    f'</div>',
    unsafe_allow_html=True,
)
