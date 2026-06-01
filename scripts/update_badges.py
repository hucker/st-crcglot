"""Regenerate the README badge SVG files from real tool output.

Runs ``ruff check``, ``ty check``, and ``pytest`` in the project
root, counts the number of errors each one finds, and writes one
SVG file per tool into ``.badges/``.  The README embeds those SVG
files via relative-path image tags (``![ruff](.badges/ruff.svg)``)
so the badges render in any markdown preview without any external
service dependency at view time.

Usage::

    uv run python scripts/update_badges.py          # rewrite .badges/
    uv run python scripts/update_badges.py --check  # exit 1 if .badges
                                                    # would change

Run the update form before pushing / opening a PR.  CI runs the
``--check`` form to catch the case where a contributor forgot.

We emit ``"0 errors"`` in green on success and ``"N errors"`` in red
otherwise, keeping the same label/format across all three tools so
the badge row reads as a uniform health strip.  SVG generation uses
``anybadge`` (no network at update time).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

import anybadge

REPO_ROOT = Path(__file__).resolve().parent.parent
BADGES_DIR = REPO_ROOT / ".badges"


class BadgeState(NamedTuple):
    """One badge worth of state -- label + error count.

    ``label`` is the prefix shown on the badge (left-side text).
    ``errors`` is the integer count of issues the tool reported.  The
    color is derived from ``errors`` (green at 0, red otherwise).
    """

    label: str
    errors: int


def _run(cmd: list[str]) -> tuple[int, str, str]:
    """Run a command, return (exit_code, stdout, stderr).

    We don't raise on non-zero exit -- every tool we care about uses
    exit code != 0 as the "issues found" signal, and we need both that
    code *and* the stdout/stderr to count the errors.
    """
    proc = subprocess.run(
        cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )
    return proc.returncode, proc.stdout, proc.stderr


def count_ruff_errors() -> int:
    """Run ``ruff check`` in JSON-output mode and count the diagnostics.

    ``ruff check --output-format json`` emits a JSON array of
    diagnostics on stdout, so we just ``len()`` it.  When ruff is clean
    the array is ``[]`` and the count is 0.
    """
    code, out, _err = _run(["uv", "run", "ruff", "check", "--output-format", "json"])
    if not out.strip():
        return 0
    try:
        diagnostics = json.loads(out)
    except json.JSONDecodeError:
        # Treat unparseable output as a single error (it's at least one
        # broken thing -- the tool itself).
        return 1
    return len(diagnostics)


def count_ty_errors() -> int:
    """Run ``ty check`` and parse the final summary line for the diagnostic count.

    ``ty`` prints a final line of the form ``Found N diagnostics`` (or
    ``Found 1 diagnostic`` -- it pluralizes correctly).  On success it
    prints ``All checks passed!``.  We parse the count from the
    summary; "passed" → 0.
    """
    code, out, err = _run(["uv", "run", "ty", "check"])
    combined = out + err
    if "All checks passed" in combined:
        return 0
    # Match "Found 8 diagnostics" / "Found 1 diagnostic"
    match = re.search(r"Found (\d+) diagnostics?", combined)
    if match:
        return int(match.group(1))
    # Tool errored without a clean summary line -- treat exit code as
    # a single failure to surface that something is wrong.
    return 1 if code != 0 else 0


def count_pytest_errors() -> int:
    """Run pytest, count failed + errored tests from the summary line.

    pytest prints a summary like ``"54 passed in 6.21s"`` on success
    and ``"1 failed, 53 passed in 6.21s"`` on failure.  Errors during
    collection produce a similar ``"1 error"`` token.  We sum the
    failed-and-errored counts; passed-only summaries give 0.
    """
    code, out, _err = _run(["uv", "run", "pytest", "-ra", "--tb=no", "-q"])
    failed = re.search(r"(\d+) failed", out)
    errored = re.search(r"(\d+) errors?", out)
    total = (int(failed.group(1)) if failed else 0) + (
        int(errored.group(1)) if errored else 0
    )
    # If pytest exits non-zero but we found no count, treat as 1 error
    # so the badge surfaces the failure.
    if code != 0 and total == 0:
        return 1
    return total


def badge_svg(state: BadgeState) -> str:
    """Render one tool's state as a Shields-style SVG string.

    Uses ``anybadge`` to produce the SVG -- same visual style as
    shields.io's static badges but generated locally, so we don't
    depend on the network at view time.
    """
    color = "green" if state.errors == 0 else "red"
    badge = anybadge.Badge(
        label=state.label, value=f"{state.errors} errors", default_color=color
    )
    return badge.badge_svg_text


def write_badge(filename: str, state: BadgeState) -> tuple[Path, str]:
    """Serialize a badge to ``.badges/<filename>``, returning (path, content).

    Returns the SVG content so callers can compare it against the
    file on disk without re-reading.
    """
    BADGES_DIR.mkdir(parents=True, exist_ok=True)
    path = BADGES_DIR / filename
    content = badge_svg(state)
    return path, content


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate .badges/*.svg from current ruff / ty / pytest results."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Don't write files; instead exit non-zero if the on-disk "
            ".badges/ would differ from what the tools currently say.  "
            "Used by CI to enforce that a contributor regenerated "
            "badges before merging."
        ),
    )
    args = parser.parse_args()

    badges = {
        "ruff.svg": BadgeState("ruff", count_ruff_errors()),
        "ty.svg": BadgeState("ty", count_ty_errors()),
        "pytest.svg": BadgeState("pytest", count_pytest_errors()),
    }

    drifted: list[str] = []
    for filename, state in badges.items():
        path, content = write_badge(filename, state)
        if args.check:
            current = path.read_text(encoding="utf-8") if path.exists() else ""
            if current != content:
                drifted.append(filename)
        else:
            path.write_text(content, encoding="utf-8")
            print(f"  wrote {path.relative_to(REPO_ROOT)}  ({state.errors} errors)")

    if args.check:
        if drifted:
            print(
                "\nERROR: .badges/ out of date.  Regenerate before committing:\n"
                "  uv run python scripts/update_badges.py\n",
                file=sys.stderr,
            )
            for f in drifted:
                print(f"  drifted: {f}", file=sys.stderr)
            return 1
        print("badges in sync with current tool output")
    return 0


if __name__ == "__main__":
    sys.exit(main())
