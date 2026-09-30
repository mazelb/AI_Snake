#!/usr/bin/env python3
"""
Structural validator for PRDs produced by the dev-flow skill.

Deterministic only. This script makes no judgement about whether a PRD is *good* —
it checks that the document is well-formed, complete, and machine-addressable, so
that downstream stages (planning, acceptance-case generation, coverage reporting)
can rely on its shape. Quality review is a separate, advisory, human/model step.

Exit codes:
    0  clean (warnings may still be present)
    1  structural errors — the document is malformed or incomplete
    2  blocked on missing input — well-formed, but contains [NEEDS INPUT: ...]

Usage:
    python validate_prd.py specs/123-cold-start/prd.md
    python validate_prd.py specs/123-cold-start/prd.md --format json
    python validate_prd.py specs/**/prd.md --quiet
"""

from __future__ import annotations

import argparse
import json
import re
import sys

# Piping into head/tail is normal usage; a broken pipe should not print a traceback.
try:
    import signal
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except (ImportError, AttributeError, ValueError):
    pass
from dataclasses import dataclass, asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from spec_lib import fingerprint  # noqa: E402

ERROR = "error"
BLOCKED = "blocked"
WARN = "warn"

REQUIRED_FRONTMATTER = ["title", "issue", "owner", "status", "created", "domain"]
VALID_STATUS = {"draft", "validated", "superseded"}
VALID_DOMAIN = {"voice-agent", "greenfield", "regulated-fintech", "general"}

REQUIRED_SECTIONS = [
    "Problem",
    "Affected users",
    "Success metric",
    "Non-goals",
    "Requirements",
    "Constraints",
    "Open questions",
]

# "Evidence" is optional — a PRD that settled nothing by building is normal.
OPTIONAL_SECTIONS = ["Evidence"]

# An evidence entry is only worth anything if it points at the artifact that
# produced it. A verdict with no branch is a recollection, not a source.
EVIDENCE_FIELDS = ["Question:", "Verdict:", "Prototype:", "Date:"]

# Words that describe a feeling rather than an observable state. Their presence in
# an acceptance condition usually means nobody can tell when the requirement is met.
VAGUE_TERMS = [
    "fast", "quick", "snappy", "responsive", "smooth", "seamless", "intuitive",
    "user-friendly", "robust", "scalable", "performant", "reliable", "clean",
    "easy to use", "better", "improved", "optimized", "as needed", "appropriate",
    "reasonable", "properly", "correctly", "efficiently",
]

NEEDS_INPUT_RE = re.compile(r"\[NEEDS INPUT:\s*([^\]]*)\]")
REQ_HEADING_RE = re.compile(r"^###\s+(REQ-\d{3})\s+\[(P[0-2])\]\s+(.+?)\s*$")
REQ_LIKE_RE = re.compile(r"^###\s+(REQ[^\s]*)")
ACCEPTANCE_RE = re.compile(r"^\*\*Acceptance:\*\*\s*(.+?)\s*$")
ISSUE_RE = re.compile(r"^[\w.\-]+/[\w.\-]+#\d+$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TEMPLATE_PLACEHOLDER_RE = re.compile(r"<[a-z][^>]{6,}>")


@dataclass
class Finding:
    level: str
    code: str
    line: int
    message: str


class Prd:
    """Minimal parse of the PRD template. Line numbers are 1-based."""

    def __init__(self, text: str):
        self.lines = text.splitlines()
        self.frontmatter: dict[str, str] = {}
        self.frontmatter_lines: dict[str, int] = {}
        self.sections: dict[str, tuple[int, int]] = {}  # name -> (start, end) 0-based
        self._parse_frontmatter()
        self._parse_sections()

    def _parse_frontmatter(self) -> None:
        if not self.lines or self.lines[0].strip() != "---":
            return
        for i, line in enumerate(self.lines[1:], start=1):
            if line.strip() == "---":
                break
            if ":" in line:
                key, _, value = line.partition(":")
                self.frontmatter[key.strip()] = value.strip()
                self.frontmatter_lines[key.strip()] = i + 1

    def _parse_sections(self) -> None:
        headings = [
            (i, line[3:].strip())
            for i, line in enumerate(self.lines)
            if line.startswith("## ")
        ]
        for idx, (line_no, name) in enumerate(headings):
            end = headings[idx + 1][0] if idx + 1 < len(headings) else len(self.lines)
            self.sections[name] = (line_no, end)

    def section_text(self, name: str) -> str:
        if name not in self.sections:
            return ""
        start, end = self.sections[name]
        return "\n".join(self.lines[start + 1 : end])

    def section_start(self, name: str) -> int:
        return self.sections.get(name, (0, 0))[0] + 1


def check_frontmatter(prd: Prd, out: list[Finding]) -> None:
    if not prd.frontmatter:
        out.append(Finding(ERROR, "frontmatter.missing", 1,
                           "No YAML frontmatter found. The document must open with a '---' block."))
        return

    for key in REQUIRED_FRONTMATTER:
        if key not in prd.frontmatter or not prd.frontmatter[key]:
            out.append(Finding(ERROR, "frontmatter.field", 1,
                               f"Frontmatter is missing required field '{key}'."))

    status = prd.frontmatter.get("status", "")
    if status and status not in VALID_STATUS:
        out.append(Finding(ERROR, "frontmatter.status", prd.frontmatter_lines.get("status", 1),
                           f"status '{status}' is not one of: {', '.join(sorted(VALID_STATUS))}."))

    domain = prd.frontmatter.get("domain", "")
    if domain and domain not in VALID_DOMAIN:
        out.append(Finding(ERROR, "frontmatter.domain", prd.frontmatter_lines.get("domain", 1),
                           f"domain '{domain}' is not one of: {', '.join(sorted(VALID_DOMAIN))}."))

    issue = prd.frontmatter.get("issue", "")
    if issue and not ISSUE_RE.match(issue):
        out.append(Finding(ERROR, "frontmatter.issue", prd.frontmatter_lines.get("issue", 1),
                           f"issue '{issue}' should look like 'owner/repo#123' so the PRD "
                           "can be traced back to the agreement it came from."))

    created = prd.frontmatter.get("created", "")
    if created and not DATE_RE.match(created):
        out.append(Finding(ERROR, "frontmatter.created", prd.frontmatter_lines.get("created", 1),
                           f"created '{created}' should be an ISO date (YYYY-MM-DD)."))


def check_sections(prd: Prd, out: list[Finding]) -> None:
    for name in REQUIRED_SECTIONS:
        if name not in prd.sections:
            out.append(Finding(ERROR, "section.missing", 1,
                               f"Required section '## {name}' is missing."))
            continue
        body = prd.section_text(name).strip()
        if not body:
            out.append(Finding(ERROR, "section.empty", prd.section_start(name),
                               f"Section '## {name}' is empty."))


def check_success_metric(prd: Prd, out: list[Finding]) -> None:
    if "Success metric" not in prd.sections:
        return
    line_no = prd.section_start("Success metric")
    body = prd.section_text("Success metric")
    for field in ("Metric:", "Current baseline:", "Target:", "Source:"):
        if field not in body:
            out.append(Finding(ERROR, "metric.field", line_no,
                               f"Success metric block is missing '{field}'."))

    # The section's body starts on the line after its heading; a finding about one
    # line points at that line, not at the heading.
    for offset, raw in enumerate(body.splitlines(), start=1):
        stripped = raw.strip().lstrip("- ").strip()
        if stripped.startswith("Target:"):
            value = stripped[len("Target:"):]
            if not NEEDS_INPUT_RE.search(value) and not re.search(r"\d", value):
                out.append(Finding(ERROR, "metric.target", line_no + offset,
                                   "Target contains no number. A target without a number "
                                   "cannot be evaluated after the fact."))
        if stripped.startswith("Source:"):
            value = stripped[len("Source:"):].strip()
            if value.startswith("prototype:"):
                continue  # a prototype branch is a legitimate source for a measured number
            if not NEEDS_INPUT_RE.search(value) and len(value) < 8:
                out.append(Finding(WARN, "metric.source", line_no,
                                   "Source is very short. Name the dashboard, event, or query "
                                   "this number is read from."))


def check_non_goals(prd: Prd, out: list[Finding]) -> None:
    if "Non-goals" not in prd.sections:
        return
    bullets = [l for l in prd.section_text("Non-goals").splitlines() if l.strip().startswith(("-", "*"))]
    if not bullets:
        out.append(Finding(ERROR, "nongoals.empty", prd.section_start("Non-goals"),
                           "Non-goals must list at least one item. A PRD with no stated "
                           "boundary invites scope expansion at the planning stage."))


def check_requirements(prd: Prd, out: list[Finding]) -> list[str]:
    if "Requirements" not in prd.sections:
        return []
    start, end = prd.sections["Requirements"]
    req_ids: list[str] = []
    blocks: list[tuple[str, int, int]] = []  # id, heading_line, end_line

    for i in range(start + 1, end):
        line = prd.lines[i]
        match = REQ_HEADING_RE.match(line)
        if match:
            req_ids.append(match.group(1))
            blocks.append((match.group(1), i, end))
            if len(blocks) > 1:
                prev = blocks[-2]
                blocks[-2] = (prev[0], prev[1], i)
        elif REQ_LIKE_RE.match(line):
            out.append(Finding(ERROR, "req.malformed", i + 1,
                               f"Requirement heading is malformed: {line.strip()!r}. "
                               "Expected '### REQ-001 [P0] short name'."))

    if not req_ids:
        out.append(Finding(ERROR, "req.none", prd.section_start("Requirements"),
                           "No requirements found. Downstream stages address work by "
                           "requirement ID, so a PRD with none cannot be planned or verified."))
        return []

    seen: set[str] = set()
    for idx, req_id in enumerate(req_ids, start=1):
        if req_id in seen:
            out.append(Finding(ERROR, "req.duplicate", 1,
                               f"{req_id} appears more than once. IDs must be unique — they are "
                               "referenced by plan tasks, acceptance cases, and PRs."))
        seen.add(req_id)
        expected = f"REQ-{idx:03d}"
        if req_id != expected:
            out.append(Finding(WARN, "req.sequence", 1,
                               f"{req_id} appears at position {idx}, expected {expected}. "
                               "Gaps are fine for withdrawn requirements — confirm this is one."))

    for req_id, head, stop in blocks:
        body_lines = prd.lines[head + 1 : stop]
        body = "\n".join(body_lines).strip()
        acceptance = None
        acceptance_line = head + 1
        for offset, line in enumerate(body_lines):
            m = ACCEPTANCE_RE.match(line.strip())
            if m:
                acceptance = m.group(1).strip()
                acceptance_line = head + offset + 2
                break

        statement = body.split("**Acceptance:**")[0].strip()
        if len(statement) < 15:
            out.append(Finding(ERROR, "req.nostatement", head + 1,
                               f"{req_id} has no statement above its acceptance condition."))

        if acceptance is None:
            out.append(Finding(ERROR, "req.noacceptance", head + 1,
                               f"{req_id} has no '**Acceptance:**' line. Every requirement needs "
                               "a condition that can be checked without asking the author."))
            continue

        if NEEDS_INPUT_RE.search(acceptance):
            continue  # reported by the needs-input scan; don't double-flag

        if len(acceptance) < 20:
            out.append(Finding(ERROR, "req.thinacceptance", acceptance_line,
                               f"{req_id} acceptance condition is too short to be checkable: "
                               f"{acceptance!r}."))

        lowered = acceptance.lower()
        hits = [t for t in VAGUE_TERMS if re.search(rf"\b{re.escape(t)}\b", lowered)]
        if hits and not re.search(r"\d", acceptance):
            out.append(Finding(WARN, "req.vague", acceptance_line,
                               f"{req_id} acceptance leans on {', '.join(repr(h) for h in hits)} "
                               "with no number. Replace with the threshold or state change "
                               "that would be observed."))

    return req_ids


def check_evidence(prd: Prd, out: list[Finding]) -> None:
    if "Evidence" not in prd.sections:
        return
    body = prd.section_text("Evidence")
    line_no = prd.section_start("Evidence")
    entries = [b for b in body.split("- Question:") if b.strip()]
    if not entries:
        return
    for entry in entries:
        chunk = "- Question:" + entry
        for field in EVIDENCE_FIELDS:
            if field not in chunk:
                out.append(Finding(ERROR, "evidence.field", line_no,
                                   f"Evidence entry is missing '{field}'. A verdict with no "
                                   "prototype branch behind it is a recollection, not a source."))
        for raw in chunk.splitlines():
            s = raw.strip().lstrip("- ")
            if s.startswith("Verdict:") and len(s[len("Verdict:"):].strip()) < 20:
                out.append(Finding(ERROR, "evidence.thinverdict", line_no,
                                   "Evidence verdict is too short to be useful. Say what was "
                                   "learned, not that something was learned."))
            if s.startswith("Prototype:"):
                branch = s[len("Prototype:"):].strip()
                if branch and not branch.startswith("proto/"):
                    out.append(Finding(WARN, "evidence.branch", line_no,
                                       f"Prototype branch {branch!r} does not start with 'proto/'. "
                                       "The convention is what keeps throwaway code findable and "
                                       "out of main."))


def check_open_questions(prd: Prd, out: list[Finding]) -> None:
    if "Open questions" not in prd.sections:
        return
    body = prd.section_text("Open questions")
    rows = [
        l for l in body.splitlines()
        if l.strip().startswith("|") and not re.match(r"^\|[\s\-|:]+\|$", l.strip())
    ]
    data_rows = [r for r in rows if "Question" not in r]
    if not data_rows and "none" not in body.lower():
        out.append(Finding(WARN, "questions.empty", prd.section_start("Open questions"),
                           "No open questions listed. That is unusual for a first draft — "
                           "if there genuinely are none, write 'None' explicitly."))
    for row in data_rows:
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if len(cells) >= 2 and not cells[1]:
            out.append(Finding(WARN, "questions.noowner", 1,
                               f"Open question has no owner: {cells[0][:60]!r}. An unowned "
                               "question does not get answered."))


def check_needs_input(prd: Prd, out: list[Finding]) -> None:
    for i, line in enumerate(prd.lines, start=1):
        for match in NEEDS_INPUT_RE.finditer(line):
            detail = match.group(1).strip() or "(unspecified)"
            out.append(Finding(BLOCKED, "input.needed", i, detail))


def check_template_leftovers(prd: Prd, out: list[Finding]) -> None:
    for i, line in enumerate(prd.lines, start=1):
        if line.strip().startswith(("|", "```")):
            continue
        if TEMPLATE_PLACEHOLDER_RE.search(line):
            out.append(Finding(ERROR, "template.leftover", i,
                               f"Unfilled template placeholder: {line.strip()[:70]!r}."))


def validate(path: Path) -> tuple[list[Finding], list[str]]:
    text = path.read_text(encoding="utf-8")
    prd = Prd(text)
    findings: list[Finding] = []
    check_frontmatter(prd, findings)
    check_sections(prd, findings)
    check_success_metric(prd, findings)
    check_non_goals(prd, findings)
    check_evidence(prd, findings)
    req_ids = check_requirements(prd, findings)
    check_open_questions(prd, findings)
    check_template_leftovers(prd, findings)
    check_needs_input(prd, findings)
    findings.sort(key=lambda f: ({ERROR: 0, BLOCKED: 1, WARN: 2}[f.level], f.line))
    return findings, req_ids


def exit_code(findings: list[Finding]) -> int:
    if any(f.level == ERROR for f in findings):
        return 1
    if any(f.level == BLOCKED for f in findings):
        return 2
    return 0


def render_text(path: Path, findings: list[Finding], req_ids: list[str], quiet: bool) -> str:
    code = exit_code(findings)
    label = {0: "PASS", 1: "FAIL (structural)", 2: "BLOCKED (needs input)"}[code]
    lines = [f"{label}  {path}"]
    if req_ids:
        lines.append(f"  requirements: {len(req_ids)} ({req_ids[0]}..{req_ids[-1]})")

    for level, heading in ((ERROR, "errors"), (BLOCKED, "blocked on input"), (WARN, "warnings")):
        group = [f for f in findings if f.level == level]
        if not group:
            continue
        if quiet and level == WARN:
            continue
        lines.append(f"\n  {heading} ({len(group)}):")
        for f in group:
            lines.append(f"    line {f.line:>4}  [{f.code}] {f.message}")

    if code == 2:
        lines.append("\n  Exit 2 is a healthy state for a first draft. Do not invent values to "
                     "clear it — route the blocked items to the people who own them.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate PRD structure.")
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--quiet", action="store_true", help="Suppress warnings in text output.")
    parser.add_argument(
        "--fingerprint", action="store_true",
        help="Print each PRD's content fingerprint and exit, without validating. "
             "This exists so /acceptance can read the fingerprint through a named "
             "script rather than a python3 -c one-liner, which would need a grant "
             "allowing arbitrary Python.")
    args = parser.parse_args()

    if args.fingerprint:
        worst = 0
        for path in args.paths:
            if not path.exists():
                print(f"FAIL  {path}: file not found", file=sys.stderr)
                worst = 1
                continue
            print(fingerprint(path))
        return worst

    worst = 0
    payload = []
    for path in args.paths:
        if not path.exists():
            print(f"FAIL  {path}: file not found", file=sys.stderr)
            worst = max(worst, 1)
            continue
        findings, req_ids = validate(path)
        code = exit_code(findings)
        worst = max(worst, code)
        if args.format == "json":
            payload.append({
                "path": str(path),
                "exit_code": code,
                "requirement_ids": req_ids,
                "findings": [asdict(f) for f in findings],
            })
        else:
            print(render_text(path, findings, req_ids, args.quiet))
            print()

    if args.format == "json":
        print(json.dumps(payload, indent=2))
    return worst


if __name__ == "__main__":
    sys.exit(main())
