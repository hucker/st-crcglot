# st-crcglot — CRC101

[![CI](https://github.com/hucker/st-crcglot/actions/workflows/ci.yml/badge.svg)](https://github.com/hucker/st-crcglot/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)

A Streamlit UI for [`crcglot`](https://github.com/hucker/crcglot): generate, calculate, and reverse-look-up CRCs against the full [reveng CRC catalogue](https://reveng.sourceforge.io/crc-catalogue/all.htm), with verified code emitters for eight target languages.

**Live app:** <https://st-crcglot-f8g7hcvqvuj58axgeok3y7.streamlit.app/>

## What it does

- **Catalog Code Gen / Custom Code Gen** — emit ready-to-compile CRC routines in C, C#, Go, Python, Rust, TypeScript, Verilog, or VHDL.  Catalog algorithms come pre-verified against reveng's published `check` values; custom algorithms take user-supplied parameters and are checked live.
- **Catalog Calc / Custom Calc** — compute the CRC of arbitrary bytes (text or hex input) and optionally verify against the catalogue check value.
- **Reverse Lookup** — paste a captured payload + trailing CRC and find which catalog algorithm produced it.  Handles both byte orderings, both text-with-hex-CRC and packed-hex-bytes framings, and common separator / prefix conventions automatically (deferred to `crcglot.detect()`).

## Run locally

Requires Python 3.14+ and [`uv`](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/hucker/st-crcglot.git
cd st-crcglot
uv run streamlit run streamlit_app.py
```

Streamlit will print the local URL it's serving on (usually <http://localhost:8501>).  The production deploy lives at the **Live app** URL above.

## Architecture

Three files:

- **[`streamlit_app.py`](streamlit_app.py)** — page structure: tabs, hero, footer.
- **[`ui.py`](ui.py)** — every streamlit render helper (pickers, sections, tab bodies).
- **[`crc_lib.py`](crc_lib.py)** — streamlit-free glue: thin wrappers around `crcglot`, plus stats persistence (Upstash Redis with local JSON fallback), version helpers, and pure-Python utilities.

All CRC logic — catalog data, computation, detection, code generation — lives in `crcglot`.  This app gathers inputs via streamlit widgets, forwards them to `crcglot`, and displays the results.

## Configuration

Counter persistence uses Upstash Redis when configured, falling back to a local JSON file otherwise.  Copy [`.streamlit/secrets.toml.example`](.streamlit/secrets.toml.example) to `.streamlit/secrets.toml` and fill in the Upstash values, or omit and use the local fallback.

For Streamlit Cloud deployments, paste the same key/value pairs into the app's **Settings → Secrets** dialog.
