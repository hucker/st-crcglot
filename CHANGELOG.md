# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `LICENSE` file (MIT) plus `license` and `authors` metadata in
  `pyproject.toml` (PEP 639 SPDX form).
- GitHub Actions CI workflow at `.github/workflows/ci.yml` running
  `ruff check`, `ruff format --check`, `ty check`, and `pytest` on
  every push / PR against `main`.
- This `CHANGELOG.md`.
- README badges (CI status, license, Python version).
- `ruff` and `ty` (Astral's type checker) added to the `dev`
  dependency group.

### Changed

- Codebase normalized to `ruff format`'s output (whitespace / line
  breaks only; no behavior change).
- Type-narrowing assertions added where the runtime already guarded
  but the static checker couldn't follow (`render_custom_picker`'s
  `parse_hex` results, `render_generate_section`'s `entry` in
  `is_custom` branch).

## [0.4.0] — 2026-05-31

The deferral release.  This version's theme is "push CRC logic out of
the Streamlit app and into crcglot, where it belongs."  After this,
`crc_lib.py` contains zero CRC math — every algorithm computation,
detection, framing decision, and code generation call goes through
crcglot.

### Added

- README with architecture overview, run-locally instructions, live
  Streamlit Cloud URL, and a "docs" link in the hero subtitle.
- pytest test suite (54 tests, ~6s runtime): 40 unit tests for
  `crc_lib.py` helpers plus 14 streamlit `AppTest` end-to-end flows
  covering the Catalog Calc gold path, Custom Calc dispatch, Code Gen
  end-to-end, Reverse Lookup (Target mode + end-of-data + no-match),
  Hex input parse error, and Target-CRC conditional rendering.

### Changed

- **Reverse Lookup, Calc, Code Gen all defer to crcglot.**  Target
  mode now uses `crcglot.detect(target_crc=...)`; end-of-data Reverse
  Lookup uses `detect(packet, mode=...)`; Catalog Calc uses
  `encode_int(data, name)`; code generation forwards the variant
  string directly via crcglot's new `variant=` kwarg.
- **All UI pills migrated from custom CSS to `st.badge`** with
  per-pill `help=` tooltips.  Section titles now use `st.subheader`.
  ~80 lines of custom CSS removed.
- **Reverse Lookup Target mode is byte-order-symmetric.**  The
  `target_crc` integer is compared against each candidate algorithm
  in both byte orderings; little-endian matches surface with an
  `Endian: Little` pill.  No manual byte-reverse step needed for
  little-endian wire captures.
- Catalog counts throughout the app (FAQ, SEO meta, picker label)
  read live `len(ALGORITHMS)` instead of hardcoded numbers.
- FAQ tab leads with the `ACKNOWLEDGMENTS`-driven "Standing on the
  shoulders of giants" section (reveng catalogue, zlib, Rocksoft
  parameterization).

### Removed

- Internal CRC helpers (~140 LOC): `_crc_compute`, `_byte_reverse`,
  `find_matching_algorithms`, `find_matching_algorithms_at_end`,
  `find_matching_algorithms_text_end`, `_kwargs_for_variant`,
  `VARIANT_ORDER`.  All replaced by crcglot calls.
- "Try big/little endian" checkbox in Reverse Lookup — `detect()`
  handles both endianness automatically.
- `crc16m` and `crc16x` catalog entries (deleted in crcglot 0.8.x as
  cruft — they were single-letter-suffix duplicates of the canonical
  `crc16-modbus` and `crc16-xmodem`).  Catalog size: 71 → 69.

### Fixed

- Reverse Lookup "Any width" vs "N-bit at end" returning different
  result sets for the same input (caused by `crcglot.detect`'s
  `mode='auto'` asymmetry on text inputs that also parsed as valid
  hex).  Worked around by forcing `mode='text'` / `mode='hex'` from
  the UI's Input format toggle.

### Dependencies

- `crcglot` bumped to `>=0.9.1, <0.10` (from `>=0.8.0, <0.9`).  The
  0.9.x line ships the `detect()` / `target_crc` / `endian` /
  `encode_int` / `variants_for_width` APIs this release depends on.

## [0.2.0] — earlier

### Added

- Initial public release.
- Streamlit UI with five flat tabs: Catalog Code Gen, Custom Code
  Gen, Catalog Calc, Custom Calc, Reverse Lookup.
- crcglot 0.7.x integration with eight target languages (C, C#, Go,
  Python, Rust, TypeScript, Verilog, VHDL).
- Test-vector display per algorithm (CRC of `b"123456789"`) and live
  verification of custom check values.
- Reverse Lookup with byte-reversed target search.
- Per-language and per-action usage counters with Upstash Redis
  persistence (production) and local JSON fallback (development).
- Hero strip, FAQ tab, dev container, secrets template.

[Unreleased]: https://github.com/hucker/st-crcglot/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/hucker/st-crcglot/compare/v0.2.0...v0.4.0
[0.2.0]: https://github.com/hucker/st-crcglot/releases/tag/v0.2.0
