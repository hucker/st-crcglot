"""Streamlit-free logic for CRC101.

This module imports no streamlit; ui.py is the only file that does.  Everything
here is pure Python: parsing, CRC search, stats I/O, crcglot wrappers, format
helpers, version helpers, and constants.  Importable from a script, a notebook,
or a pytest suite without spinning up a streamlit runtime.
"""

from __future__ import annotations

import functools
import json
import os
import re
import subprocess
import tomllib
from importlib.metadata import PackageNotFoundError, version as pkg_version
from pathlib import Path
from typing import Literal

from crcglot import (
    ALGORITHMS,
    AlgorithmInfo,
    CrcStream,  # noqa: F401  -- re-exported through ui.py
    GeneratedFile,
    LANGUAGES,
    NAMING_ORDER,  # noqa: F401  -- re-exported through ui.py
    ReverseResult,
    crc_stream,  # noqa: F401  -- re-exported through ui.py
    default_stem,  # noqa: F401  -- re-exported through ui.py
    detect,
    encode_int,
    generate_files,
    generic_crc,
    naming_info,  # noqa: F401  -- re-exported through ui.py
    reverse_packets,
    variant_info,
)
from crcglot.comments import style_info

# Optional / newer symbol -- isolated so a missing or stale crcglot can't
# crash the whole app at import time.  Empty tuple = FAQ credits section
# is omitted; everything else keeps working.
try:
    from crcglot import ACKNOWLEDGMENTS
except ImportError:
    ACKNOWLEDGMENTS = ()

# crcglot symbols re-exported so ui.py only needs to import from crc_lib.
__all__ = [
    "ACKNOWLEDGMENTS",
    "ALGORITHMS",
    "AlgorithmInfo",
    "LANGUAGES",
    "REPO_URL",
    "APP_ROOT",
    "STATS_FILE",
    "CALC_KEY",
    "REVERSE_KEY",
    "RECOVER_KEY",
    "SENTINEL_CUSTOM",
    "VARIANT_ICONS",
    "GeneratedFile",
    "ReverseResult",
    "catalogue_names",
    "encode_int",
    "generic_crc",
    "parse_hex",
    "parse_hex_bytes",
    "detect_chunk",
    "recover_packets",
    "padding_pills",
    "variant_info",
    "style_info",
    "available_variants",
    "available_variants_bundle",
    "generate_source_files",
    "default_stem",
    "alg_label",
    "lang_label",
    "variant_label",
    "style_label",
    "load_stats",
    "bump_stats",
    "app_version",
    "crcglot_version",
    "git_revision",
]


# ---------- Module-level constants ----------

REPO_URL = "https://github.com/hucker/st-crcglot"
# This module lives at src/crc_lib.py; APP_ROOT walks up to the repo
# root so pyproject.toml (read by app_version), crcglot_stats.json
# (stats fallback), and git rev-parse (run with cwd=APP_ROOT) all
# resolve correctly.
APP_ROOT = Path(__file__).resolve().parent.parent
STATS_FILE = APP_ROOT / "crcglot_stats.json"
CALC_KEY = "__calculate__"  # not a language code -- excluded from per-lang pills.
REVERSE_KEY = "__reverse__"  # ditto -- Identify (catalogue-match) tab counter.
RECOVER_KEY = "__recover__"  # ditto -- Recover Custom (reverse-engineer) tab counter.
SENTINEL_CUSTOM = "__custom__"  # passed as `name` when generating from custom params.

# Icons are app-side aesthetic, not part of crcglot's variant model;
# labels and descriptions read live from `crcglot.variant_info()` so they
# stay in sync with the library and the CLI.
VARIANT_ICONS: dict[str, str] = {
    "bitwise": "◯",
    "table": "▦",
    "slice8": "▩",
}

# Width ascending, then name ascending: groups crc8 -> 16 -> 32 -> 64 in the picker.
catalogue_names = sorted(
    ALGORITHMS,
    key=lambda n: (ALGORITHMS[n].width, n),
)

_HEX_STRIP_RE = re.compile(r"0x|0X|[:,\s]")


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
    except OSError, KeyError, tomllib.TOMLDecodeError:
        return "unknown"


@functools.cache
def crcglot_version() -> str:
    """Read the installed crcglot package version.

    Reads :data:`crcglot.__version__` directly (added upstream alongside
    the variant_info / styles helpers).  Falls back to package metadata
    if the running crcglot somehow lacks the attribute -- shouldn't
    happen in practice given our ``>=0.14`` pin, but keeps the footer
    safe under mixed dev environments.

    Cached for the process lifetime.

    Returns:
        The PEP 440 version string, or ``"unknown"`` if crcglot isn't
        importable / installed (shouldn't happen -- it's a hard dep).
    """
    try:
        import crcglot

        return getattr(crcglot, "__version__", None) or pkg_version("crcglot")
    except ImportError, PackageNotFoundError:
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
        dirty = (
            subprocess.call(
                ["git", "diff-index", "--quiet", "HEAD", "--"],
                cwd=APP_ROOT,
                stderr=subprocess.DEVNULL,
            )
            != 0
        )
        return f"{sha}-dirty" if dirty else sha
    except OSError:
        return "unknown"


# ---------- Stats I/O ----------
#
# Counters can live in one of two backends:
#
# 1. Upstash Redis (production / Streamlit Community Cloud) -- set the
#    UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN env vars (Streamlit
#    Cloud reads these from .streamlit/secrets.toml and promotes them to env
#    vars automatically).  Counter keys are prefixed ``crc101:`` to avoid
#    clashes with anything else in the Redis instance.  INCR is atomic so
#    concurrent bumps don't lose counts.
#
# 2. Local JSON file (default / local dev) -- fall back to crcglot_stats.json
#    in the app root.  Single-process, no concurrency safety, but zero setup.

_UPSTASH_URL = os.environ.get("UPSTASH_REDIS_REST_URL")
_UPSTASH_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN")

if _UPSTASH_URL and _UPSTASH_TOKEN:
    from upstash_redis import Redis as _UpstashRedis

    _redis: _UpstashRedis | None = _UpstashRedis(url=_UPSTASH_URL, token=_UPSTASH_TOKEN)
else:
    _redis = None

_REDIS_PREFIX = "crc101:"


def _all_counter_keys() -> list[str]:
    """The set of counter keys the footer reads -- per-language plus the
    two sentinel keys."""
    return list(LANGUAGES) + [CALC_KEY, REVERSE_KEY, RECOVER_KEY]


def _load_stats_local() -> dict[str, int]:
    try:
        raw = json.loads(STATS_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError, json.JSONDecodeError, OSError:
        return {}
    return {k: int(v) for k, v in raw.items() if isinstance(v, (int, float))}


def _bump_stats_local(key: str) -> dict[str, int]:
    stats = _load_stats_local()
    stats[key] = stats.get(key, 0) + 1
    tmp = STATS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(stats), encoding="utf-8")
    tmp.replace(STATS_FILE)
    return stats


def load_stats() -> dict[str, int]:
    """Load the persisted usage counters.

    Returns:
        A dict mapping counter key (language code, :data:`CALC_KEY`, or
        :data:`REVERSE_KEY`) to its integer count.  Missing keys are
        omitted.  Returns an empty dict when the backend is unreachable
        or unconfigured with no local file present.
    """
    if _redis is None:
        return _load_stats_local()
    try:
        keys = _all_counter_keys()
        values = _redis.mget(*[f"{_REDIS_PREFIX}{k}" for k in keys])
        return {k: int(v) for k, v in zip(keys, values) if v is not None}
    except Exception:
        # Never let a counter-backend failure break the UI.  Falls through
        # to an empty dict; the footer will render zeros.
        return {}


def bump_stats(key: str) -> dict[str, int]:
    """Increment the counter for ``key``.

    Uses Upstash's atomic ``INCR`` when configured -- safe under concurrent
    reruns and across deployment replicas.  Falls back to a non-atomic
    read-modify-write on the local JSON file otherwise.  Failures in
    either backend are swallowed silently; counters are best-effort and
    must not break the user-facing action.

    Args:
        key: The counter to bump.  Typically a crcglot language code
            (``"c"``, ``"python"``, ...), :data:`CALC_KEY`, or
            :data:`REVERSE_KEY`.

    Returns:
        The complete updated stats dict (same shape as :func:`load_stats`).
    """
    if _redis is None:
        return _bump_stats_local(key)
    try:
        _redis.incr(f"{_REDIS_PREFIX}{key}")
    except Exception:
        pass
    return load_stats()


# ---------- Pure helpers ----------


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


DetectMode = Literal["auto", "binary", "text", "hex"]


def detect_chunk(
    chunk: bytes | str,
    width: int | None = None,
    mode: DetectMode | None = None,
    target_crc: int | None = None,
) -> list[tuple[str, AlgorithmInfo, str | None, object | None]]:
    """Find catalog algorithms whose CRC sits at the end of a single chunk.

    Thin wrapper around :func:`crcglot.detect`.  We pass the chunk in
    single-packet form (no multi-packet intersection) and surface the
    candidates in the ``(name, info, endian, padding)`` shape the renderer
    consumes.  ``mode`` is forced rather than letting ``detect``'s
    ``mode="auto"`` guess -- auto-mode currently picks differently
    depending on whether an ``algorithms`` filter was passed, which made
    "Any width" and "<N>-bit at end" disagree on text inputs that *look*
    like hex.

    Args:
        chunk: Bytes (binary packet) or str (text or hex-encoded packet).
            In end-of-data mode (``target_crc=None``) this is payload +
            trailing CRC; in target_crc mode this is data only.
        width: Optional CRC width filter in bits (8 / 16 / 32 / 64).
            Translated to the algorithm glob ``"crc<width>*"`` -- a clean
            one-to-one match against the catalogue.  ``None`` means search
            every width.
        mode: ``"text"`` / ``"hex"`` / ``"binary"``.  When ``None``
            (default), inferred from the chunk type: str -> ``"text"``,
            bytes -> ``"binary"``.  Pass ``"hex"`` explicitly to ask
            crcglot to hex-decode a string into bytes first.
        target_crc: When supplied, treat ``chunk`` as data only (no CRC
            extracted from the tail) and find catalog algorithms whose
            CRC of the data equals this value.  In this mode the
            returned ``endian`` is always ``"Big"`` and ``padding`` is
            ``None`` -- crcglot doesn't byte-parse a CRC in this path.

    Returns:
        A list of ``(name, info, endian, padding)`` tuples.  ``name`` is
        the catalog key (e.g. ``"crc32"``) since ``AlgorithmInfo`` no
        longer carries it as a field.  ``endian`` is ``"Big"`` or
        ``"Little"``.  ``padding`` is crcglot's ``TextFormat`` /
        ``HexFormat`` describing how the boundary was parsed, or ``None``
        (binary input, or ``target_crc`` mode).
    """
    glob = f"crc{width}*" if width else None
    if mode is None:
        mode = "text" if isinstance(chunk, str) else "binary"
    result = detect(
        chunk,
        mode=mode,
        match="all",
        algorithms=glob,
        target_crc=target_crc,
    )
    return [
        (
            cand.algorithm,
            cand.info,
            "Little" if cand.endianness == "little" else "Big",
            cand.padding,
        )
        for cand in result.candidates
    ]


def recover_packets(
    frames_text: str,
    *,
    crc_bytes: int | None = None,
    crc_byte_order: Literal["big", "little", "both"] = "big",
    std_algo_only: bool = False,
) -> ReverseResult:
    """Reverse-engineer an unknown / custom CRC from sample frames.

    Thin wrapper around :func:`crcglot.reverse_packets`.  The newline-
    separated ``frames_text`` is split into one hex frame per line --
    each line is a whole captured frame (payload + trailing CRC) -- and
    decoded to bytes via :func:`parse_hex_bytes` (which strips ``0x``
    prefixes, ``:`` / ``,`` separators, and whitespace).  Everything
    about the actual parameter search -- candidate enumeration,
    ambiguity scoring, catalogue cross-check -- lives in crcglot; we
    only marshal input and hand back its :class:`ReverseResult`.

    Args:
        frames_text: Newline-separated hex frames; blank lines ignored.
            Each non-blank line is payload + trailing CRC, where the
            last ``crc_bytes`` bytes are the CRC field.
        crc_bytes: Width of the trailing CRC field in bytes (1 / 2 / 4
            / 8 -> 8 / 16 / 32 / 64-bit).  ``None`` (the default) lets
            crcglot search every width.
        crc_byte_order: Byte order of the trailing CRC field --
            ``"big"``, ``"little"``, or ``"both"`` to try each.
        std_algo_only: When ``True``, restrict the search to catalogue
            algorithms; when ``False`` (the default for this path) allow
            fully custom parameter sets -- the whole reason this is a
            separate workflow from :func:`detect_chunk`.

    Returns:
        crcglot's :class:`ReverseResult` -- ``status``, ``candidates``
        (each an :class:`AlgorithmInfo` carrying the recovered
        ``width`` / ``poly`` / ``init`` / ``refin`` / ``refout`` /
        ``xorout``), ``catalogue_name`` if the recovered parameters
        happen to match a known algorithm, ``ambiguity_bits`` (how
        underdetermined the solution is -- more frames drives it
        toward 0), ``validated_frames``, and a human-readable ``note``.

    Raises:
        ValueError: No non-blank frames, or a line fails hex decoding.
    """
    frames: list[bytes] = [
        parse_hex_bytes(line) for line in frames_text.splitlines() if line.strip()
    ]
    if not frames:
        raise ValueError("Provide at least one hex frame (one per line).")
    return reverse_packets(
        frames,
        crc_bytes=crc_bytes,
        crc_byte_order=crc_byte_order,
        std_algo_only=std_algo_only,
    )


def _human_separator(sep: str) -> str:
    """Name a separator string for display -- keyboard-key words for
    whitespace, literal backtick form for visible punctuation.

    Args:
        sep: The raw separator (e.g. ``" "``, ``"\\t"``, ``":"``, ``""``).

    Returns:
        ``"NONE"`` for empty, ``"SPACE"`` / ``"TAB"`` / ``"NEWLINE"`` /
        ``"CRLF"`` for single whitespace chars, ``"<n> SPACES"`` /
        ``"<n> TABS"`` for runs of the same whitespace, otherwise the raw
        string wrapped in backticks for inline-code rendering.
    """
    if not sep:
        return "NONE"
    if sep == " ":
        return "SPACE"
    if sep == "\t":
        return "TAB"
    if sep == "\n":
        return "NEWLINE"
    if sep == "\r\n":
        return "CRLF"
    if all(c == " " for c in sep):
        return f"{len(sep)} SPACES"
    if all(c == "\t" for c in sep):
        return f"{len(sep)} TABS"
    return f"`{sep}`"


def padding_pills(padding: object | None) -> list[tuple[str, str]]:
    """Return per-pill ``(label, help)`` pairs for a ``DetectMatch.padding``.

    Used to surface ``detect()``'s boundary interpretation so the user can
    verify it matches what they pasted.  Each pair maps to one
    :func:`streamlit.badge` call: the label goes on the badge, the help
    string powers its click-tooltip.  Empty list for binary input
    (``padding=None``) since there's no boundary ambiguity to describe.

    Args:
        padding: The ``padding`` attribute of a ``DetectMatch`` --
            ``TextFormat`` (text mode), ``HexFormat`` (hex-text auto-decode
            mode), or ``None`` (binary mode).

    Returns:
        A list of ``(label, help_markdown)`` tuples in render order:
        separator, then prefix (when present), then case.  Empty list when
        there's nothing to describe.
    """
    if padding is None:
        return []

    pills: list[tuple[str, str]] = []

    # Separator: both TextFormat and HexFormat have one, under different names.
    sep = getattr(padding, "separator", None)
    if sep is None:
        sep = getattr(padding, "byte_separator", None)
    if sep is not None:
        pills.append(
            (
                f"Sep: {_human_separator(sep)}",
                "Character `detect()` found between the payload and the hex "
                "CRC in the input.\n\n"
                "- `SPACE` / `TAB` / `NEWLINE` / `CRLF` for whitespace.\n"
                "- Punctuation shown literally (e.g. `` `:` ``, `` `,` ``).\n"
                "- `NONE` if the CRC sat directly against the payload.",
            )
        )

    # Prefix: TextFormat.hex_prefix, HexFormat.prefix (+ prefix_per_byte flag).
    prefix = getattr(padding, "hex_prefix", None)
    if prefix is None:
        prefix = getattr(padding, "prefix", None)
    if prefix:
        per_byte = " (per byte)" if getattr(padding, "prefix_per_byte", False) else ""
        pills.append(
            (
                f"Prefix: {prefix}{per_byte}",
                "A hex prefix (typically `0x`) detected immediately before "
                "the CRC.  `(per byte)` means every byte in the input was "
                "prefixed individually, not just the trailing CRC.",
            )
        )

    # Case of the hex CRC characters.
    case = "Upper" if getattr(padding, "uppercase", False) else "Lower"
    pills.append(
        (
            f"Hex: {case}",
            "Case of the hex digits in the input: `Upper` (e.g. `CBF43926`) "
            "or `Lower` (e.g. `cbf43926`).",
        )
    )

    return pills


# ---------- crcglot wrappers ----------


def available_variants(code: str, width: int) -> list[str]:
    """Return the implementation variants a language supports at a given width.

    Deferred to ``LanguageInfo.variants_for_width`` -- crcglot owns the
    "which variants work at which widths" rule (e.g. slice8 only
    pays off at 32 / 64).

    Args:
        code: crcglot language code (e.g. ``"c"``, ``"python"``).
        width: CRC width in bits.

    Returns:
        Variant codes in canonical display order (as returned by
        crcglot: bitwise, table, slice8).
    """
    return list(LANGUAGES[code].variants_for_width(width))


def available_variants_bundle(code: str, widths: list[int]) -> list[str]:
    """Variants compatible with EVERY width in a multi-algorithm bundle.

    crcglot's combiner emits one variant across every bundled algorithm,
    so the offered variants have to be the intersection of what each
    algorithm's width supports (e.g. ``slice8`` only at 32/64 means
    bundling a 16-bit CRC with a 32-bit one drops slice8 from the picker).

    Args:
        code: crcglot language code.
        widths: Widths of the algorithms in the bundle, in any order.
            Empty list returns the language's full default variant order.

    Returns:
        Variants in canonical order (bitwise, table, slice8), filtered to
        those every width supports.  Always non-empty: bitwise works
        everywhere, so worst-case the picker shows just bitwise.
    """
    info = LANGUAGES[code]
    if not widths:
        return list(info.variants)
    result = list(info.variants_for_width(widths[0]))
    for w in widths[1:]:
        compat = set(info.variants_for_width(w))
        result = [v for v in result if v in compat]
    return result


def generate_source_files(
    lang: str,
    *,
    names: str | list[str] | None = None,
    entry: AlgorithmInfo | None = None,
    variant: str,
    symbol: str,
    comment_style: str = "plain",
    naming: str | None = None,
) -> tuple[GeneratedFile, ...]:
    """Generate ready-to-write source file(s); crcglot owns the filenames.

    Thin wrapper over :func:`crcglot.generate_files`, which owns both the
    output filename and the in-code (class / module / function) naming and
    returns :class:`GeneratedFile` records (``filename`` / ``content`` /
    ``role``) the caller writes verbatim.  This replaces the old app-side
    ``f"{symbol}{ext}"`` derivation -- and the single-vs-bundle branching,
    which ``generate_files`` now handles internally.

    Exactly one of ``names`` (catalog) or ``entry`` (custom) must be given.

    The app's ``symbol`` field maps to crcglot's ``name=`` (single / custom)
    or ``file_stem=`` (bundle), never ``symbol=``: crcglot's ``symbol=`` is a
    verbatim escape hatch that *raises* for Java, whereas ``name=`` is the
    one knob valid in every mode (and cased per target).  A bundle rejects
    ``name=`` / ``symbol=`` entirely, so the value becomes ``file_stem=``
    there -- each bundled algorithm keeps its catalogue-derived function
    name; the value just sets the container / file base.

    Args:
        lang: crcglot language code.
        names: One catalog algorithm name (``str``) or several
            (``list[str]``).  Mutually exclusive with ``entry``.
        entry: A custom :class:`AlgorithmInfo`.  Mutually exclusive with
            ``names``.
        variant: ``"bitwise"`` / ``"table"`` / ``"slice8"``.
        symbol: The user's basename; routed to crcglot's ``name=`` /
            ``file_stem=`` as described above.  Empty string -> crcglot's
            own default base.
        comment_style: Documentation comment style; see
            :func:`crcglot.comments.styles_for_language` for the codes
            valid for ``lang``.
        naming: Naming convention (``"snake"`` / ``"camel"`` / ``"pascal"``)
            or ``None`` to use the language's default -- the latter is the
            right choice for targets that don't offer ``snake`` (e.g. Java).

    Returns:
        A tuple of :class:`GeneratedFile`; one entry for single-file
        languages, two (header + source) for C.
    """
    sym = symbol or None
    if entry is not None:
        return generate_files(
            lang,
            custom=entry,
            variant=variant,
            comment_style=comment_style,
            naming=naming,
            name=sym,
        )
    if isinstance(names, list) and len(names) > 1:
        return generate_files(
            lang,
            names,
            variant=variant,
            comment_style=comment_style,
            naming=naming,
            file_stem=sym,
        )
    one = names[0] if isinstance(names, list) else names
    return generate_files(
        lang,
        one,
        variant=variant,
        comment_style=comment_style,
        naming=naming,
        name=sym,
    )


# ---------- Format helpers ----------


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
        e.g. ``"◯  Bit-by-bit"`` or ``"▦  Table-driven"`` -- icon from
        the local :data:`VARIANT_ICONS` map, label from
        :func:`crcglot.variant_info`.
    """
    return f"{VARIANT_ICONS[v]}  {variant_info(v).label}"


def style_label(s: str) -> str:
    """Format a comment-style code for the picker.

    Args:
        s: Style code (e.g. ``"plain"``, ``"doxygen"``, ``"javadoc"``).

    Returns:
        The human label from :func:`crcglot.comments.style_info`
        (e.g. ``"Doxygen"``, ``"JavaDoc"``).  No icon prefix -- styles
        are documentation conventions, not implementation choices, so
        a glyph would carry no semantic meaning.
    """
    return style_info(s).label
