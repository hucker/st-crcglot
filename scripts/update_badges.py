"""Update the README's shields.io badge URLs from real tool output.

Runs ``ruff check``, ``ty check``, and ``pytest`` in the project
root, counts the number of errors each one finds, then rewrites the
shields.io static-badge URLs between the ``BADGES:BEGIN`` /
``BADGES:END`` markers in the README so they reflect current state.

shields.io static badges have the form::

    https://img.shields.io/badge/<LABEL>-<MESSAGE>-<COLOR>

The badge text and color are encoded directly in the URL -- no
external JSON file, no caching service except shields.io's own
short-lived edge cache.  The URL *is* the data: when the script
rewrites the URL, the next view fetches a fresh SVG from shields.io.

Usage::

    uv run python scripts/update_badges.py          # update README badges
    uv run python scripts/update_badges.py --check  # exit 1 if README
                                                    # would change

Run the update form before pushing / opening a PR.  CI runs the
``--check`` form to catch the case where a contributor forgot.

The README must contain a line-per-badge block bracketed by HTML
comments::

    <!-- BADGES:BEGIN -->
    ![ruff](https://img.shields.io/badge/...)
    ![ty](https://img.shields.io/badge/...)
    ![pytest](https://img.shields.io/badge/...)
    <!-- BADGES:END -->

Anything between the markers is replaced.  Adding a new tool means
adding a count_xxx_errors() function and an entry in the BADGES list
below; the script regenerates the whole block.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parent.parent
README = REPO_ROOT / "README.md"
BEGIN_MARKER = "<!-- BADGES:BEGIN -->"
END_MARKER = "<!-- BADGES:END -->"


class BadgeState(NamedTuple):
    """One badge's worth of state -- label + error count.

    ``label`` is the prefix shown on the badge (left side).
    ``errors`` is the integer count of issues the tool reported.  Color
    is derived from ``errors`` (green at 0, red otherwise).
    """

    label: str
    errors: int


def _run(cmd: list[str]) -> tuple[int, str, str]:
    """Run a command, return (exit_code, stdout, stderr).

    We don't raise on non-zero exit -- every tool we care about uses
    a non-zero code as the "issues found" signal, and we need both that
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
    _code, out, _err = _run(["uv", "run", "ruff", "check", "--output-format", "json"])
    if not out.strip():
        return 0
    try:
        diagnostics = json.loads(out)
    except json.JSONDecodeError:
        # Treat unparseable output as a single error (something is broken
        # at the tool level -- still surfaces in the badge).
        return 1
    return len(diagnostics)


def count_ty_errors() -> int:
    """Run ``ty check`` and parse the final summary line for the diagnostic count.

    ``ty`` prints a final line of the form ``Found N diagnostics``
    (it pluralizes correctly).  On success it prints
    ``All checks passed!``.  We parse the count from the summary;
    "passed" → 0.
    """
    code, out, err = _run(["uv", "run", "ty", "check"])
    combined = out + err
    if "All checks passed" in combined:
        return 0
    match = re.search(r"Found (\d+) diagnostics?", combined)
    if match:
        return int(match.group(1))
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
    # If pytest exited non-zero but we found no count, treat as 1 error
    # so the badge surfaces the failure rather than silently showing 0.
    if code != 0 and total == 0:
        return 1
    return total


def badge_url(state: BadgeState) -> str:
    """Build a shields.io static badge URL for one tool's state.

    shields.io URL format::

        https://img.shields.io/badge/<LABEL>-<MESSAGE>-<COLOR>

    Spaces in the message are URL-encoded as ``%20``.  We also
    URL-encode hyphens as ``--`` per shields.io's escaping rules (a
    raw ``-`` would be parsed as a field separator).
    """
    color = "brightgreen" if state.errors == 0 else "red"
    label = state.label.replace("-", "--").replace(" ", "%20")
    message = f"{state.errors} errors".replace("-", "--").replace(" ", "%20")
    return f"https://img.shields.io/badge/{label}-{message}-{color}"


def render_badge_block(states: list[BadgeState]) -> str:
    """Render the full BADGES:BEGIN..END block, with markers."""
    lines = [BEGIN_MARKER]
    for state in states:
        lines.append(f"![{state.label}]({badge_url(state)})")
    lines.append(END_MARKER)
    return "\n".join(lines)


_BLOCK_RE = re.compile(
    re.escape(BEGIN_MARKER) + r".*?" + re.escape(END_MARKER),
    re.DOTALL,
)


def rewrite_readme(new_block: str) -> tuple[str, str]:
    """Return (old_readme, new_readme) with the badge block replaced.

    Raises if the markers are missing -- a stronger signal than a
    silent no-op, since the caller likely deleted the markers by
    accident.
    """
    text = README.read_text(encoding="utf-8")
    if not _BLOCK_RE.search(text):
        raise SystemExit(
            f"README does not contain a {BEGIN_MARKER!r}..{END_MARKER!r} block. "
            f"Add the markers around the existing badges first."
        )
    return text, _BLOCK_RE.sub(new_block, text, count=1)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Rewrite README.md's shields.io badge URLs based on "
            "current ruff / ty / pytest results."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Don't write the README; instead exit non-zero if the "
            "current badge block would differ from what the tools "
            "report.  Used by CI to enforce that a contributor "
            "regenerated badges before merging."
        ),
    )
    args = parser.parse_args()

    states = [
        BadgeState("ruff", count_ruff_errors()),
        BadgeState("ty", count_ty_errors()),
        BadgeState("pytest", count_pytest_errors()),
    ]
    new_block = render_badge_block(states)
    old_readme, new_readme = rewrite_readme(new_block)

    if args.check:
        if old_readme != new_readme:
            print(
                "\nERROR: README badge block out of date.  "
                "Regenerate before committing:\n"
                "  uv run python scripts/update_badges.py\n",
                file=sys.stderr,
            )
            return 1
        print("badge block in sync with current tool output")
        return 0

    README.write_text(new_readme, encoding="utf-8")
    for s in states:
        print(f"  {s.label}: {s.errors} errors")
    return 0


if __name__ == "__main__":
    sys.exit(main())
