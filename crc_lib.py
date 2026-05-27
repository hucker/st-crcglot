"""Streamlit-free logic for CRC101.

This module imports no streamlit; ui.py is the only file that does.  Everything
here is pure Python: parsing, CRC search, stats I/O, crcglot wrappers, format
helpers, version helpers, and constants.  Importable from a script, a notebook,
or a pytest suite without spinning up a streamlit runtime.
"""
from __future__ import annotations

import functools
import json
import re
import subprocess
import tomllib
from importlib.metadata import PackageNotFoundError, version as pkg_version
from pathlib import Path

from crcglot import (
    ALGORITHMS,
    AlgorithmInfo,
    LANGUAGES,
    generic_crc,
)

# crcglot symbols re-exported so ui.py only needs to import from crc_lib.
__all__ = [
    "ALGORITHMS",
    "AlgorithmInfo",
    "LANGUAGES",
    "REPO_URL",
    "APP_ROOT",
    "STATS_FILE",
    "CALC_KEY",
    "REVERSE_KEY",
    "SENTINEL_CUSTOM",
    "VARIANTS",
    "VARIANT_ORDER",
    "catalogue_names",
    "_crc_compute",
    "_byte_reverse",
    "parse_hex",
    "parse_hex_bytes",
    "find_matching_algorithms",
    "find_matching_algorithms_at_end",
    "find_matching_algorithms_text_end",
    "available_variants",
    "generate_catalogue",
    "generate_custom",
    "default_symbol",
    "alg_label",
    "lang_label",
    "variant_label",
    "load_stats",
    "bump_stats",
    "app_version",
    "crcglot_version",
    "git_revision",
]


# ---------- Module-level constants ----------

REPO_URL = "https://github.com/hucker/st-crcglot"
APP_ROOT = Path(__file__).resolve().parent
STATS_FILE = APP_ROOT / "crcglot_stats.json"
CALC_KEY = "__calculate__"      # not a language code -- excluded from per-lang pills.
REVERSE_KEY = "__reverse__"     # ditto -- reverse-lookup tab counter.
SENTINEL_CUSTOM = "__custom__"  # passed as `name` when generating from custom params.

VARIANTS: dict[str, tuple[str, str, str]] = {
    "bitwise": ("◯", "Bit-by-bit",   "Smallest; portable; one byte per 8 shifts."),
    "table":   ("▦", "Table-driven", "256-entry LUT; 4-8x faster than bit-by-bit."),
    "slice8":  ("▩", "Slice-by-8",   "8 LUTs; another 5-10x faster (32/64-bit CRCs only)."),
}
VARIANT_ORDER: tuple[str, ...] = ("bitwise", "table", "slice8")

# Width ascending, then name ascending: groups crc8 -> 16 -> 32 -> 64 in the picker.
catalogue_names = sorted(
    ALGORITHMS, key=lambda n: (ALGORITHMS[n].width, n),
)

_HEX_STRIP_RE = re.compile(r"0x|0X|[:,\s]")

# Internal alias kept for ui.py compatibility (was the streamlit-time import name).
_crc_compute = generic_crc


# ---------- Version helpers ----------

@functools.cache
def app_version() -> str:
    """Read this app's semver from ``pyproject.toml``.

    Cached for the process lifetime so repeated calls don't re-read the file.

    Returns:
        The ``project.version`` string, or ``"unknown"`` if pyproject.toml is
        missing, malformed, or missing the field.
    """
    try:
        data = tomllib.loads((APP_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        return data["project"]["version"]
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return "unknown"


@functools.cache
def crcglot_version() -> str:
    """Read the installed crcglot package version.

    Cached for the process lifetime.

    Returns:
        The PEP 440 version string from package metadata, or ``"unknown"``
        if crcglot isn't installed (shouldn't happen in practice -- it's a
        hard dependency).
    """
    try:
        return pkg_version("crcglot")
    except PackageNotFoundError:
        return "unknown"


def git_revision() -> str:
    """Return the short git SHA of ``HEAD``, with a ``-dirty`` suffix when
    tracked files have been modified.

    Not cached so a streamlit-watch reload after a commit shows the new SHA
    without restarting the server.  Uses ``rev-parse`` (not ``describe``) so
    the rev is always the short SHA -- otherwise being on a release tag
    would echo back the same string we already show via :func:`app_version`
    next to it.  Untracked files don't count as dirty; only modified tracked
    files do.

    Returns:
        The short SHA (e.g. ``"cfbd07a"``), the SHA with ``"-dirty"``
        suffix when the working tree has unstaged or staged changes to
        tracked files, or ``"unknown"`` if git is unavailable or the
        ``rev-parse`` call fails.
    """
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=APP_ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        if not sha:
            return "unknown"
        dirty = subprocess.call(
            ["git", "diff-index", "--quiet", "HEAD", "--"],
            cwd=APP_ROOT,
            stderr=subprocess.DEVNULL,
        ) != 0
        return f"{sha}-dirty" if dirty else sha
    except OSError:
        return "unknown"


# ---------- Stats I/O ----------

def load_stats() -> dict[str, int]:
    """Load the persisted usage counters from ``crcglot_stats.json``.

    Returns:
        A dict mapping counter key (language code, ``CALC_KEY``, or
        ``REVERSE_KEY``) to its integer count.  Returns an empty dict when
        the file is missing, unreadable, or contains malformed JSON.
        Non-numeric values are silently skipped during the read.
    """
    try:
        raw = json.loads(STATS_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return {k: int(v) for k, v in raw.items() if isinstance(v, (int, float))}


def bump_stats(key: str) -> dict[str, int]:
    """Increment the counter for ``key`` and persist the updated dict.

    Uses an atomic tmp-file write so a crash mid-update doesn't leave a
    truncated stats file.  Not thread-safe under concurrent reruns; see the
    earlier docs note about concurrency.

    Args:
        key: The counter to bump.  Typically a crcglot language code
            (``"c"``, ``"python"``, ...), :data:`CALC_KEY`, or
            :data:`REVERSE_KEY`.

    Returns:
        The complete updated stats dict (same shape as :func:`load_stats`).
    """
    stats = load_stats()
    stats[key] = stats.get(key, 0) + 1
    tmp = STATS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(stats), encoding="utf-8")
    tmp.replace(STATS_FILE)
    return stats


# ---------- Pure helpers ----------

def _byte_reverse(value: int, width: int) -> int | None:
    """Reverse the byte order of ``value`` interpreted at ``width`` bits.

    For example, ``_byte_reverse(0x12345678, 32)`` returns ``0x78563412``.

    Args:
        value: The integer to reverse.  Must fit in ``width`` bits.
        width: Bit width of the value.  Must be a positive multiple of 8 so
            the value packs into whole bytes.

    Returns:
        The byte-reversed integer, or ``None`` when reversal isn't
        well-defined: ``width`` not a positive multiple of 8, or ``value``
        out of range for that width.
    """
    if width <= 0 or width % 8:
        return None
    n = width // 8
    if value < 0 or value >= (1 << width):
        return None
    return int.from_bytes(value.to_bytes(n, "big")[::-1], "big")


def parse_hex(raw: str, label: str, width: int) -> tuple[int | None, str | None]:
    """Parse a single hex integer constrained to ``width`` bits.

    Accepts ``0x`` / ``0X`` prefix or bare hex.  Leading/trailing whitespace
    is stripped.

    Args:
        raw: The raw user-supplied string (e.g. ``"0xFF"`` or ``"04C11DB7"``).
        label: Field name used in error messages (e.g. ``"Polynomial"``).
        width: Maximum width in bits.  Values exceeding ``(1 << width) - 1``
            are rejected.

    Returns:
        A ``(value, error_msg)`` pair.  On success: ``(int_value, None)``.
        On failure: ``(None, "..." error message)`` with a UI-friendly
        explanation suitable for ``st.error``.
    """
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


def parse_hex_bytes(s: str) -> bytes:
    """Parse a hex dump into a bytes object.

    Strips ``0x`` / ``0X`` prefixes, ``:``, ``,``, and all whitespace from
    ``s`` first, then consumes the remainder as consecutive two-nibble
    hex pairs.  Suitable for parsing pasted hex dumps in any common format
    (``"DEADBEEF"``, ``"de ad be ef"``, ``"0xCA:0xFE"``, etc.).

    Args:
        s: The input string.

    Returns:
        The parsed bytes.  An empty input (or one that contains only
        separators) returns ``b""``.

    Raises:
        ValueError: With a UI-friendly message when the cleaned remainder
            contains non-hex characters or has an odd number of nibbles.
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


# ---------- Search ----------

def find_matching_algorithms(
    data: bytes,
    target: int,
    try_endian: bool = False,
) -> list[tuple[AlgorithmInfo, str | None]]:
    """Search the catalog for algorithms producing ``target`` on ``data``.

    Args:
        data: The input bytes that the algorithm's CRC should produce
            ``target`` over.
        target: The CRC value to match.  Tested against each algorithm's
            CRC of ``data``; algorithms whose width can't represent
            ``target`` are skipped.
        try_endian: When True, also tests :func:`_byte_reverse` of the
            target for each algorithm whose width is a multiple of 8 --
            catches the common endianness mismatch where the captured CRC
            bytes were transcribed in the opposite order from what the
            protocol uses on the wire.

    Returns:
        A list of ``(info, annotation)`` tuples for each match.
        ``annotation`` is ``None`` for a direct match or
        ``"opposite endianness"`` when only the byte-reversed comparison hit.
    """
    matches: list[tuple[AlgorithmInfo, str | None]] = []
    for info in ALGORITHMS.values():
        target_rev = _byte_reverse(target, info.width) if try_endian else None
        mask = (1 << info.width) - 1
        if target > mask and (target_rev is None or target_rev > mask):
            continue
        value = _crc_compute(
            data, info.width, info.poly, info.init,
            info.refin, info.refout, info.xorout,
        )
        if target <= mask and value == target:
            matches.append((info, None))
        elif target_rev is not None and target_rev <= mask and value == target_rev:
            matches.append((info, "opposite endianness"))
    return matches


def find_matching_algorithms_text_end(
    text: str,
    width: int,
    try_endian: bool = False,
) -> list[tuple[AlgorithmInfo, str | None, str, int]]:
    """Reverse-lookup against text whose trailing chars are a hex CRC.

    Because this is a reverse lookup -- the user is *guessing* both the
    algorithm and the framing -- we try several plausible boundary
    interpretations and return matches annotated with which one hit:

        - **strict**: last ``width//4`` chars are the hex CRC, everything
          before is the payload.
        - **0x prefix peeled**: if the chars immediately before the
          trailing hex are ``0x`` or ``0X``, peel them.
        - Each of the above with the payload's trailing whitespace
          stripped.

    Args:
        text: Full input string (payload concatenated with trailing hex
            CRC, possibly with whitespace and/or ``0x`` prefix in between).
        width: CRC width in bits.  Must satisfy ``width % 4 == 0`` and the
            text must have at least ``width // 4`` characters.  Catalog
            search is restricted to algorithms of this width.
        try_endian: Forwarded to :func:`find_matching_algorithms` -- when
            True, also tests the byte-reversed target per algorithm.

    Returns:
        A list of ``(info, endian_annotation, boundary_label, payload_len)``
        tuples, deduped by ``(info.name, payload_bytes, target,
        endian_annotation)``.  Empty when the text is too short or the
        trailing chars under no interpretation parse as hex.
    """
    hex_chars = width // 4
    if width <= 0 or width % 4 or len(text) < hex_chars:
        return []

    def is_hex(s: str) -> bool:
        return bool(s) and all(c in "0123456789abcdefABCDEF" for c in s)

    # Build the list of boundary interpretations.  Each entry is
    # (payload_text, crc_hex_text, label).
    variants: list[tuple[str, str, str]] = []

    # Strict: last hex_chars are the CRC.
    trail = text[-hex_chars:]
    if is_hex(trail):
        variants.append((text[:-hex_chars], trail, "strict"))

    # 0x prefix peel: if the chars immediately before the trailing hex are
    # "0x" or "0X", treat those 2 chars as a prefix to discard.
    if len(text) >= hex_chars + 2:
        prefix = text[-(hex_chars + 2):-hex_chars]
        if prefix.lower() == "0x" and is_hex(trail):
            variants.append(
                (text[:-(hex_chars + 2)], trail, "0x prefix peeled")
            )

    # Add whitespace-stripped versions of each variant where stripping
    # actually changes the payload.
    for v_pay, v_crc, v_label in list(variants):
        stripped = v_pay.rstrip()
        if stripped != v_pay:
            variants.append(
                (stripped, v_crc, f"{v_label} + trailing whitespace stripped")
            )

    if not variants:
        return []

    # Search each variant; dedupe so multiple boundary interpretations
    # producing the same (payload, target) only yield one row per algorithm.
    seen: set[tuple[str, bytes, int, str | None]] = set()
    results: list[tuple[AlgorithmInfo, str | None, str, int]] = []
    for payload_text, crc_text, label in variants:
        payload_bytes = payload_text.encode("utf-8")
        target = int(crc_text, 16)
        raw = find_matching_algorithms(payload_bytes, target, try_endian=try_endian)
        for info, endian_ann in raw:
            if info.width != width:
                continue
            key = (info.name, payload_bytes, target, endian_ann)
            if key in seen:
                continue
            seen.add(key)
            results.append((info, endian_ann, label, len(payload_bytes)))
    return results


def find_matching_algorithms_at_end(
    data: bytes,
    width: int,
    try_endian: bool = True,
) -> list[tuple[AlgorithmInfo, str | None]]:
    """Search the catalog assuming the trailing bytes of ``data`` are the CRC.

    Takes the last ``width // 8`` bytes of ``data`` as the candidate CRC and
    everything before as the payload to hash.  Restricts the search to
    catalog algorithms whose width matches.

    Args:
        data: Full captured bytes -- payload + trailing CRC.
        width: CRC width in bits.  Must be a positive multiple of 8.  Only
            algorithms with exactly this width are tested.
        try_endian: When True (default), tests both big-endian and
            little-endian interpretations of the trailing bytes.  When
            False, only big-endian.

    Returns:
        A list of ``(info, annotation)`` tuples for each match.
        ``annotation`` is ``None`` for a direct big-endian match (the
        natural reading), or ``"opposite endianness"`` when only the
        little-endian interpretation matched.  Returns ``[]`` if ``width``
        isn't a positive multiple of 8, or if ``data`` is shorter than the
        trailing CRC width.
    """
    if width <= 0 or width % 8:
        return []
    n = width // 8
    if len(data) < n:
        return []
    payload = data[:-n]
    crc_bytes = data[-n:]
    target_be = int.from_bytes(crc_bytes, "big")
    target_le = int.from_bytes(crc_bytes, "little")

    matches: list[tuple[AlgorithmInfo, str | None]] = []
    for info in ALGORITHMS.values():
        if info.width != width:
            continue
        value = _crc_compute(
            payload, info.width, info.poly, info.init,
            info.refin, info.refout, info.xorout,
        )
        if value == target_be:
            # Direct (BE) match -- emit no extra annotation.  For width 8
            # BE == LE so there's literally no distinction to draw.
            matches.append((info, None))
        elif try_endian and target_be != target_le and value == target_le:
            matches.append((info, "opposite endianness"))
    return matches


# ---------- crcglot wrappers ----------

def available_variants(code: str, width: int) -> list[str]:
    """Return the implementation variants a language supports at a given width.

    Filters :data:`VARIANT_ORDER` against the language's declared
    ``variants`` set and drops ``"slice8"`` for widths other than 32 / 64
    (it only pays off as an optimization at those native sizes).

    Args:
        code: crcglot language code (e.g. ``"c"``, ``"python"``).
        width: CRC width in bits.

    Returns:
        Variant codes in canonical display order (bitwise, table, slice8).
    """
    supported = LANGUAGES[code].variants
    return [
        v for v in VARIANT_ORDER
        if v in supported and not (v == "slice8" and width not in (32, 64))
    ]


def _kwargs_for_variant(variant: str) -> dict:
    """Translate a variant name into the kwargs that crcglot generators accept.

    Args:
        variant: One of ``"bitwise"``, ``"table"``, ``"slice8"``.

    Returns:
        Empty dict for bitwise (the generator's default); ``{"table": True}``
        for table; ``{"slice8": True}`` for slice-by-8.
    """
    if variant == "table":
        return {"table": True}
    if variant == "slice8":
        return {"slice8": True}
    return {}


def generate_catalogue(lang: str, name: str, variant: str, symbol: str):
    """Generate code for a named catalog algorithm.

    Args:
        lang: crcglot language code.
        name: Catalog algorithm name (e.g. ``"crc32"``).
        variant: ``"bitwise"`` / ``"table"`` / ``"slice8"``.
        symbol: Function / file basename to use in the generated code.

    Returns:
        The generator's output -- a source string for single-file languages,
        or a tuple of strings for multi-file languages (e.g. C's ``.h``/``.c``).
    """
    return LANGUAGES[lang].generator(
        name, symbol=symbol or None, **_kwargs_for_variant(variant),
    )


def generate_custom(lang: str, name: str, entry: AlgorithmInfo, variant: str, symbol: str):
    """Generate code from a custom :class:`AlgorithmInfo` instead of a name.

    Args:
        lang: crcglot language code.
        name: Logical name for the algorithm (used in comments / function
            naming when ``symbol`` is empty).
        entry: The user-built :class:`AlgorithmInfo` describing the CRC
            parameters.
        variant: ``"bitwise"`` / ``"table"`` / ``"slice8"``.
        symbol: Function / file basename to use in the generated code.

    Returns:
        The generator's output -- shape mirrors :func:`generate_catalogue`.
    """
    return LANGUAGES[lang].generator_from_entry(
        name, entry, symbol=symbol or None, **_kwargs_for_variant(variant),
    )


# ---------- Format helpers ----------

def default_symbol(name: str) -> str:
    """Convert a catalog algorithm name into a default function/file basename.

    Args:
        name: Catalog name (e.g. ``"crc16-modbus"``).

    Returns:
        The same string with hyphens replaced by underscores
        (e.g. ``"crc16_modbus"``).
    """
    return name.replace("-", "_")


def alg_label(name: str) -> str:
    """Format a catalog algorithm name for the picker selectbox.

    Args:
        name: Catalog name (e.g. ``"crc16-modbus"``).

    Returns:
        A ``"CRC-W  ·  name"`` string, e.g. ``"CRC-16  ·  crc16-modbus"``.
    """
    w = ALGORITHMS[name].width
    return f"CRC-{w:<2}  ·  {name}"


def lang_label(k: str) -> str:
    """Format a language code as ``"emoji  display_name"`` for the picker.

    Args:
        k: crcglot language code (e.g. ``"c"``, ``"python"``).

    Returns:
        e.g. ``"🐍  Python"``.
    """
    info = LANGUAGES[k]
    return f"{info.emoji}  {info.display_name}"


def variant_label(v: str) -> str:
    """Format an implementation variant for the picker.

    Args:
        v: Variant key (``"bitwise"`` / ``"table"`` / ``"slice8"``).

    Returns:
        e.g. ``"◯  Bit-by-bit"`` or ``"▦  Table-driven"``.
    """
    icon, name, _ = VARIANTS[v]
    return f"{icon}  {name}"
