#!/usr/bin/env python3
"""
Trace test results back to acceptance cases.

The problem this solves: acceptance cases live in markdown as AC-001..N, the tests
live in whatever runner the project uses, and nothing connects them. Without a
connection, "the suite passed" tells you nothing about whether the requirements
were met — which is the entire question.

The connection is a naming convention, not an integration. Every generated test
carries its case id in its name:

    test("AC-002 state survives a disconnection", ...)
    def test_ac_003_in_flight_turn_never_ambiguous():

There are two ways to read the results.

  - **JUnit XML**, when `flow.json` sets `acceptance_junit` to the report file the
    `acceptance` command writes, or `--junit PATH` names one. Each `<testcase>`
    whose `name` carries an id passes, or fails if it holds a `<failure>` or
    `<error>`; a skipped one gives no verdict. The runner's text output is then
    drained, never scraped. Prefer this whenever the runner can write the report:
    it cannot mistake a word in a test title for a verdict.

  - **The runner's text output**, otherwise. Scraping is crude on purpose: it works
    with any runner in any language that prints test names, which is the only way
    to stay language-agnostic without an adapter per ecosystem. What keeps it
    honest is where it looks. A verdict counts only in a verdict position:
      * the line's first token, after indentation and runner decoration: a status
        glyph (✓ ✔ √ pass; ✗ ✕ × ✘ ✖ fail), TAP's `ok` / `not ok`, Playwright's
        `ok` / `x` on a legacy Windows console, Jest's and Vitest's `PASS` / `FAIL`,
        pytest's `PASSED` / `FAILED` / `ERROR` summary lines, unittest's `FAIL:` /
        `ERROR:`, go's `--- PASS:` / `--- FAIL:`, dotnet's `Passed` / `Failed`;
      * or its last token, after a `...` (unittest, cargo) or on a pytest node-id
        line (`path::test PASSED [ 50%]`), once a trailing duration, progress or
        retry note is set aside; or rspec's trailing `(FAILED - N)`.
    Verdict words match whole and in the case runners print them, so the "ok" in
    "lookup" or "token", or "error" in a test's title, is not a verdict. A line
    with an id but no verdict in a verdict position gives that id nothing.

A case with no verdict reports as MISSING, never as passing: silence is never
success here. A fail anywhere wins over a pass.

A JUnit report must come from the run being traced, or it would replay an old
run as this one. Piped in (`<cmd> | ac_trace.py`), the report must have been
written after this script started, less 2 s for timestamp granularity. With
`--output FILE` (the run has finished), it must have been written no more than
60 s before FILE was last written. A report that is absent, stale or not XML is
exit 3, never a quiet fallback to scraping.

Usage:
    <test command> 2>&1 | python3 ac_trace.py specs/14-slug/acceptance.md
    python3 ac_trace.py specs/14-slug/acceptance.md --output results.txt
    python3 ac_trace.py specs/14-slug/acceptance.md --junit report.xml [--output results.txt]

Exit codes: 0 all cases pass · 1 a case failed · 2 a case has no test (MISSING;
reported over a fail) · 3 nothing to trace (no acceptance file or cases, no
runner output file, flow.json unreadable, or the JUnit report absent, stale or
unreadable)
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

# Taken first: in the pipe form the runner starts at the same moment as this
# script, so a JUnit report written before now is from an earlier run.
STARTED = time.time()

sys.path.insert(0, str(Path(__file__).parent))
import pipeline_config  # noqa: E402
from spec_lib import AC_HEADING_RE, Doc  # noqa: E402

# Piping into head/tail is normal usage; a broken pipe is not an error worth a
# traceback.
try:
    import signal
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except (ImportError, AttributeError, ValueError):
    pass

# Matches AC-001, ac-001, ac_001 and AC001 — test-name conventions differ per
# language (kebab in JS test titles, snake in Python function names), so the
# convention has to survive both.
# \b cannot be used here: in a snake_case test name like test_ac_001_offline the
# underscores are word characters, so there is no boundary either side of "ac".
# Explicit lookaround instead, which also stops "MAC-001" matching.
AC_RE = re.compile(r"(?<![A-Za-z0-9])[Aa][Cc][-_ ]?(\d{3})(?![0-9])")

PIPE_SLACK_S = 2      # the pipe form: report written after this script started, less this
OUTPUT_WINDOW_S = 60  # --output: report written at most this long before the output file

# --- text output ---------------------------------------------------------------

# Colour and cursor codes, in case the runner was forced to colour a pipe.
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")

# Runner decoration before the verdict: go's `---`, pytest-xdist's worker `[gw0]`
# and progress `[ 50%]`, Playwright's worker index `[0]`.
LEAD_DECOR_RE = re.compile(r"^(?:(?:---|\[gw\d+\]|\[\d+\]|\[\s*\d+%\])\s+)+")

# Status glyphs are unambiguous, so they count as the line's first character
# even with nothing between them and what follows.
PASS_GLYPHS = "✓✔√"
FAIL_GLYPHS = "✗✕×✘✖"

# Verdict words as runners print them, case included. `ok` and `x` are also
# Playwright's `list` marks on a Windows console that is neither VS Code nor
# Windows Terminal (packages/playwright/src/reporters/list.ts:28-30).
LEAD_PASS = {"ok", "PASS", "PASSED", "Passed"}
LEAD_FAIL = {"x", "FAIL", "FAILED", "Failed", "ERROR"}
TRAIL_PASS = {"ok", "PASSED"}
TRAIL_FAIL = {"FAILED", "FAIL", "ERROR"}

# Trailing notes that are not the verdict: `(5 ms)`, `(1.2s)`, `[ 50%]`,
# `[100%]`, Playwright's `(retry #1)`. Set aside one at a time from the end.
TRAIL_NOISE_RE = re.compile(
    r"\s*(?:\(\s*\d+(?:\.\d+)?\s*(?:ms|s|m)\s*\)|\[\s*\d+%\]|\(retry #\d+\))\s*$")

# rspec's documentation format marks a failure at the end: `... (FAILED - 1)`.
RSPEC_FAIL_RE = re.compile(r"\(FAILED - \d+\)\s*$")

# A TAP directive: `ok 3 - AC-003 # SKIP` is a skipped test, not a pass.
TAP_DIRECTIVE_RE = re.compile(r"#\s*(?:SKIP|TODO)\b", re.I)


def line_verdict(line: str) -> str | None:
    """'pass' | 'fail' | None for one line of runner output, ANSI codes removed."""
    rest = LEAD_DECOR_RE.sub("", line.strip())
    if not rest or TAP_DIRECTIVE_RE.search(rest):
        return None

    # Leading position.
    if rest[0] in FAIL_GLYPHS:
        return "fail"
    if rest[0] in PASS_GLYPHS:
        return "pass"
    tokens = rest.split()
    first = tokens[0].rstrip(":")
    if first == "not" and len(tokens) > 1 and tokens[1] == "ok":
        return "fail"
    if first in LEAD_FAIL:
        return "fail"
    if first in LEAD_PASS:
        return "pass"

    # Trailing position.
    if RSPEC_FAIL_RE.search(rest):
        return "fail"
    tail = rest
    while (shorter := TRAIL_NOISE_RE.sub("", tail)) != tail:
        tail = shorter
    parts = tail.rsplit(None, 1)
    if len(parts) != 2:
        return None
    before, last = parts
    if not (before.endswith("...") or "::" in before):
        return None
    if last in TRAIL_FAIL:
        return "fail"
    if last in TRAIL_PASS:
        return "pass"
    return None


def merge(results: dict[str, str], ids: list[str], verdict: str) -> None:
    for num in ids:
        ac = f"AC-{num}"
        if results.get(ac) == "fail":
            continue
        results[ac] = verdict


def parse_output(text: str) -> dict[str, str]:
    """Map AC id -> 'pass' | 'fail' from runner text. A fail anywhere wins over a pass."""
    results: dict[str, str] = {}
    for raw in text.splitlines():
        line = ANSI_RE.sub("", raw)
        ids = AC_RE.findall(line)
        if not ids:
            continue
        verdict = line_verdict(line)
        if verdict is not None:
            merge(results, ids, verdict)
    return results


# --- JUnit XML -----------------------------------------------------------------

class TraceError(Exception):
    """Nothing trustworthy to trace against: exit 3."""


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_junit(path: Path) -> dict[str, str]:
    """Map AC id -> 'pass' | 'fail' from a JUnit XML report.

    Only a testcase's `name` is searched for ids. `classname` is the file or the
    class, and a file named after one case would otherwise lend that case every
    verdict in the file. The runner's own outcome is taken as it is: a flaky test
    that the runner counts as passed (no `<failure>`) passes here too.
    """
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        raise TraceError(f"JUnit report {path} is not readable XML: {exc}") from exc
    results: dict[str, str] = {}
    for case in root.iter():
        if not isinstance(case.tag, str) or _local(case.tag) != "testcase":
            continue
        ids = AC_RE.findall(case.get("name", ""))
        if not ids:
            continue
        children = {_local(child.tag) for child in case if isinstance(child.tag, str)}
        if children & {"failure", "error"}:
            merge(results, ids, "fail")
        elif "skipped" not in children:
            merge(results, ids, "pass")
    return results


def check_fresh(report: Path, output: Path | None) -> None:
    """Raise TraceError unless the report was written by the run being traced."""
    try:
        written = report.stat().st_mtime
    except OSError:
        raise TraceError(f"JUnit report not found: {report}. The acceptance command "
                         "should write it (flow.json `acceptance_junit`).") from None
    if output is None:
        if written < STARTED - PIPE_SLACK_S:
            raise TraceError(
                f"JUnit report {report} is stale: written {STARTED - written:.0f}s before "
                "this trace started, so it is from an earlier run. Pipe the acceptance "
                "command into this script, or pass a finished run's output with --output.")
    else:
        ref = output.stat().st_mtime
        if written < ref - OUTPUT_WINDOW_S:
            raise TraceError(
                f"JUnit report {report} is stale: written {ref - written:.0f}s before "
                f"{output} was last written (more than {OUTPUT_WINDOW_S}s), so it is "
                "from an earlier run.")


# --- main ----------------------------------------------------------------------

def junit_from_config() -> Path | None:
    """flow.json's `acceptance_junit` in the working directory, or None when unset."""
    try:
        cfg = pipeline_config.load()
    except SystemExit:  # load() has already said why flow.json is unreadable
        raise TraceError("flow.json could not be read") from None
    if cfg is None:
        return None
    problems = pipeline_config.junit_problems(cfg.data)
    if problems:
        raise TraceError(f"{cfg.path}: {problems[0]}")
    value = cfg.acceptance_junit
    return Path(value) if value else None


def read_text(output: Path | None) -> str:
    # Bytes, decoded as UTF-8: on Windows a piped stdin and read_text() are cp1252,
    # which turns every ✓ and ✘ into mojibake that no marker matches.
    data = output.read_bytes() if output else sys.stdin.buffer.read()
    return data.decode("utf-8", errors="replace")


def main() -> int:
    ap = argparse.ArgumentParser(description="Trace test output to acceptance cases.")
    ap.add_argument("acceptance", type=Path)
    ap.add_argument("--output", type=Path,
                    help="read runner output from a file instead of stdin")
    ap.add_argument("--junit", type=Path,
                    help="read verdicts from this JUnit XML report "
                         "(default: flow.json's acceptance_junit, when set)")
    args = ap.parse_args()

    if not args.acceptance.exists():
        print(f"acceptance file not found: {args.acceptance}", file=sys.stderr)
        return 3

    doc = Doc(args.acceptance)
    cases = []
    for block in doc.blocks(AC_HEADING_RE, "# "):
        heading = doc.lines[block.start]
        match = AC_HEADING_RE.match(heading)
        cases.append({
            "id": block.id,
            "req": match.group(2),
            "name": match.group(3),
            "type": block.fields().get("type", "").lower(),
        })

    if not cases:
        print(f"no acceptance cases found in {args.acceptance}", file=sys.stderr)
        return 3

    if args.output and not args.output.is_file():
        print(f"runner output not found: {args.output}", file=sys.stderr)
        return 3

    try:
        report = args.junit or junit_from_config()
        # Take the whole of the runner's output first, report or not: in the pipe
        # form the report is written as the run ends, and leaving early would cut
        # the runner's pipe.
        text = read_text(args.output)
        if report is not None:
            check_fresh(report, args.output)
            results = parse_junit(report)
            source = f"JUnit report {report.as_posix()}"
        else:
            results = parse_output(text)
            source = "runner output (text)"
    except TraceError as exc:
        print(str(exc), file=sys.stderr)
        return 3

    worst = 0
    rows = []
    for case in cases:
        verdict = results.get(case["id"])
        if verdict == "pass":
            mark, note = "PASS   ", ""
        elif verdict == "fail":
            mark, note = "FAIL   ", ""
            worst = max(worst, 1)
        elif case["type"] == "manual":
            mark, note = "MANUAL ", "run by hand — not traceable from test output"
        else:
            mark, note = "MISSING", "no test carries this id"
            worst = max(worst, 2)
        rows.append(f"  {mark} {case['id']} [{case['req']}] {case['name'][:44]}"
                    + (f"  — {note}" if note else ""))

    automated = [c for c in cases if c["type"] != "manual"]
    passed = sum(1 for c in automated if results.get(c["id"]) == "pass")
    print(f"{args.acceptance}")
    print(f"  {passed}/{len(automated)} automated cases passing "
          f"({len(cases) - len(automated)} manual), read from {source}")
    print()
    print("\n".join(rows))

    if worst == 2:
        print("\n  MISSING cases are not passes. Either generate the test (/harness) or "
              "\n  move the case under 'Not covered' with a reason.")
    return worst


if __name__ == "__main__":
    sys.exit(main())
