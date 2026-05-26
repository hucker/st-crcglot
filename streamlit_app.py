"""Streamlit UI for crcglot -- generate CRC code in C, Python, Rust, or VHDL."""
from __future__ import annotations

import streamlit as st
from crcglot import CRC_CATALOGUE, GENERATORS, GENERATORS_FROM_ENTRY

LANGUAGES: dict[str, tuple[str, str, str]] = {
    "c":      ("⚙️", "C / C++", "c"),
    "python": ("\U0001F40D",   "Python",  "py"),
    "rust":   ("\U0001F980",   "Rust",    "rs"),
    "vhdl":   ("\U0001F50C",   "VHDL",    "vhd"),
    "csharp": ("\U0001F4A0",   "C#",      "cs"),
    "go":     ("\U0001F6A6",   "Go",      "go"),
    "zig":    ("⚡",       "Zig",     "zig"),
}

VARIANTS: dict[str, tuple[str, str, str]] = {
    "bitwise": ("◯", "Bit-by-bit",   "Smallest; portable; one byte per 8 shifts."),
    "table":   ("▦", "Table-driven", "256-entry LUT; 4-8x faster than bit-by-bit."),
    "slice8":  ("▩", "Slice-by-8",   "8 LUTs; another 5-10x faster (32/64-bit CRCs only)."),
}

SENTINEL_CUSTOM = "__custom__"


def available_variants(lang: str, width: int) -> list[str]:
    # VHDL generator only emits bit-by-bit; its table= flag is a no-op.
    if lang == "vhdl":
        return ["bitwise"]
    out = ["bitwise", "table"]
    # Slice-by-8 is a high-throughput optimization that only makes sense
    # at widths 32/64, in imperative languages with native integer types.
    if lang in ("c", "rust", "csharp", "go", "zig") and width in (32, 64):
        out.append("slice8")
    return out


def _kwargs_for_variant(variant: str) -> dict:
    if variant == "table":
        return {"table": True}
    if variant == "slice8":
        return {"slice8": True}
    return {}


def generate_catalogue(lang: str, name: str, variant: str, symbol: str):
    return GENERATORS[lang](name, symbol=symbol or None, **_kwargs_for_variant(variant))


def generate_custom(lang: str, name: str, entry: dict, variant: str, symbol: str):
    return GENERATORS_FROM_ENTRY[lang](
        name, entry, symbol=symbol or None, **_kwargs_for_variant(variant),
    )


def default_symbol(name: str) -> str:
    return name.replace("-", "_")


def alg_label(name: str) -> str:
    if name == SENTINEL_CUSTOM:
        return "✏️  Custom — enter your own parameters"
    w = CRC_CATALOGUE[name]["width"]
    return f"CRC-{w:<2}  ·  {name}"


def lang_label(k: str) -> str:
    icon, name, _ = LANGUAGES[k]
    if k not in GENERATORS:
        return f"{icon}  {name}  · soon"
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
    CRC_CATALOGUE, key=lambda n: (CRC_CATALOGUE[n]["width"], n),
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
        entry = dict(CRC_CATALOGUE[name])
        width = entry["width"]
        custom_error: str | None = None
    else:
        seed = CRC_CATALOGUE[st.session_state.last_catalogue_name]
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
                refin = st.checkbox("Reflect input (refin)", value=bool(seed["refin"]))
            with r1c2:
                width = st.number_input(
                    "Width (bits)",
                    min_value=1, max_value=64,
                    value=int(seed["width"]),
                    step=1,
                    help="CRC register width, 1-64 bits.",
                )
            with r1c3:
                poly_raw = st.text_input("Polynomial (hex)", value=hex(seed["poly"]))
            with r1c4:
                init_raw = st.text_input("Init (hex)", value=hex(seed["init"]))

            r2c1, r2c2, r2c3, r2c4 = st.columns(4, vertical_alignment="bottom")
            with r2c1:
                refout = st.checkbox("Reflect output (refout)", value=bool(seed["refout"]))
            with r2c2:
                check_raw = st.text_input(
                    "Check (hex)",
                    value=hex(seed["check"]),
                    help='CRC of the ASCII bytes "123456789". Used by the generated self-test.',
                )
            with r2c3:
                xorout_raw = st.text_input("Xorout (hex)", value=hex(seed["xorout"]))
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

        if custom_error:
            st.error(custom_error)
            entry = {}
        else:
            entry = {
                "width": int(width), "poly": poly, "init": init,
                "refin": refin, "refout": refout,
                "xorout": xorout, "check": check, "desc": desc,
            }

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
        cat = CRC_CATALOGUE[name]
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Width",      f"{cat['width']} bits")
        m2.metric("Polynomial", hex(cat["poly"]))
        m3.metric("Init",       hex(cat["init"]))
        m4.metric("Check",      hex(cat["check"]))

        with st.expander("All parameters (reflect / xorout / description)"):
            st.json({
                k: (hex(v) if isinstance(v, int) and k != "width" else v)
                for k, v in cat.items()
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
    lang_unavailable = lang not in GENERATORS
    with btn_col:
        go = st.button(
            "Generate code",
            type="primary",
            disabled=(
                (not symbol.strip())
                or lang_unavailable
                or (is_custom and custom_error is not None)
            ),
            use_container_width=True,
            icon=":material/play_arrow:",
        )

    if lang_unavailable:
        st.info(
            f"**{LANGUAGES[lang][1]}** support is on the way in the next "
            f"`crcglot` release. The UI is wired up and ready; selecting the "
            f"language today previews the picker but cannot generate code yet."
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

    with st.container(border=True):
        st.markdown('<span class="crc-section">Output</span>', unsafe_allow_html=True)

        if lang == "c":
            header, source = result
            h_col, c_col = st.columns(2)
            with h_col:
                st.markdown(f"**\U0001F4C4 `{symbol}.h`**  ·  *{len(header):,} bytes*")
                st.code(header, language="c", line_numbers=True)
                st.download_button(
                    "Download .h", header,
                    file_name=f"{symbol}.h", mime="text/x-c",
                    use_container_width=True, icon=":material/download:",
                )
            with c_col:
                st.markdown(f"**\U0001F4C4 `{symbol}.c`**  ·  *{len(source):,} bytes*")
                st.code(source, language="c", line_numbers=True)
                st.download_button(
                    "Download .c", source,
                    file_name=f"{symbol}.c", mime="text/x-c",
                    use_container_width=True, icon=":material/download:",
                )
        else:
            _, _, ext = LANGUAGES[lang]
            st.markdown(f"**\U0001F4C4 `{symbol}.{ext}`**  ·  *{len(result):,} bytes*")
            st.code(result, language=lang, line_numbers=True)
            st.download_button(
                f"Download .{ext}", result,
                file_name=f"{symbol}.{ext}", mime="text/plain",
                use_container_width=True, icon=":material/download:",
            )
