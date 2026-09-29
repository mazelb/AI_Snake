#!/usr/bin/env python3
"""
Shared parsing for the spec pipeline artifacts.

Deliberately dependency-free and deliberately dumb: it reads structure, never
meaning. Every judgement in this pipeline belongs to a human or to a model call
that is advisory — nothing here decides whether an artifact is any good.
"""

from __future__ import annotations

import hashlib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# The scripts that import this print arrows and dashes, and run on both a Mac and a Windows box,
# where Python's stdout codec is cp1252 whenever output is piped or redirected --
# which is how every command's context line runs them. cp1252 cannot encode "→",
# so without this the script dies with a traceback and exits 1. Same fix as
# issue_envelope.py.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # already wrapped, or not a real stream
        pass

ERROR = "error"
BLOCKED = "blocked"
WARN = "warn"

NEEDS_INPUT_RE = re.compile(r"\[NEEDS INPUT:\s*([^\]]*)\]")
TEMPLATE_PLACEHOLDER_RE = re.compile(r"<[a-z][^>]{6,}>")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ISSUE_RE = re.compile(r"^[\w.\-]+/[\w.\-]+#\d+$")

REQ_ID_RE = re.compile(r"\bREQ-\d{3}\b")
REQ_HEADING_RE = re.compile(r"^###\s+(REQ-\d{3})\s+\[(P[0-2])\]\s+(.+?)\s*$")
TASK_HEADING_RE = re.compile(r"^###\s+(TASK-\d{3})\s+(.+?)\s*$")
AC_HEADING_RE = re.compile(r"^##\s+(AC-\d{3})\s+\[(REQ-\d{3})\]\s+(.+?)\s*$")
FIELD_RE = re.compile(r"^\s*[-*]\s*([A-Za-z ]+):\s*(.*)$")

# A task in a plan that skips the PRD cites the issue instead: `Satisfies: #42`.
# The lookbehind keeps `owner/repo#42` and `abc#42` from counting as a citation.
ISSUE_REF_RE = re.compile(r"(?<![\w/])#(\d+)\b")

# The steps a plan may list under `## Skipped steps`. Only these two are named as
# skippable by the decisions (build C6 amending K4 and Q5): the PRD, and the
# acceptance cases. Anything else listed there is an unknown skip, which the plan
# validator rejects -- failing closed until a decision adds a step.
SKIPPABLE_STEPS = ("prd", "acceptance")
SKIP_SECTION = "Skipped steps"
# The shortest reason accepted for a skip, or for `Seams: none — <reason>`. Below
# this it is a word, not a reason ("n/a", "trivial").
MIN_REASON = 10


@dataclass
class Finding:
    level: str
    code: str
    line: int
    message: str


@dataclass
class Block:
    """A heading and the lines beneath it, up to the next heading of the same level."""
    id: str
    name: str
    start: int          # 0-based line index of the heading
    lines: list[str] = field(default_factory=list)

    @property
    def body(self) -> str:
        return "\n".join(self.lines).strip()

    def fields(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for line in self.lines:
            m = FIELD_RE.match(line)
            if m:
                out[m.group(1).strip().lower()] = m.group(2).strip()
        return out


class Doc:
    def __init__(self, path: Path):
        self.path = path
        self.text = path.read_text(encoding="utf-8")
        self.lines = self.text.splitlines()
        self.frontmatter: dict[str, str] = {}
        self._parse_frontmatter()

    def _parse_frontmatter(self) -> None:
        if not self.lines or self.lines[0].strip() != "---":
            return
        for line in self.lines[1:]:
            if line.strip() == "---":
                break
            if ":" in line:
                key, _, value = line.partition(":")
                self.frontmatter[key.strip()] = value.strip()

    def blocks(self, pattern: re.Pattern, level: str) -> list[Block]:
        """Collect heading blocks matching pattern, ending at the next heading of `level`."""
        out: list[Block] = []
        current: Block | None = None
        for i, line in enumerate(self.lines):
            m = pattern.match(line)
            if m:
                if current:
                    out.append(current)
                groups = m.groups()
                current = Block(id=groups[0], name=groups[-1], start=i)
                continue
            if current is not None and line.startswith(level):
                out.append(current)
                current = None
                continue
            if current is not None:
                current.lines.append(line)
        if current:
            out.append(current)
        return out

    def needs_input(self) -> list[tuple[int, str]]:
        found = []
        for i, line in enumerate(self.lines, start=1):
            for m in NEEDS_INPUT_RE.finditer(line):
                found.append((i, m.group(1).strip() or "(unspecified)"))
        return found

    def placeholders(self) -> list[tuple[int, str]]:
        found = []
        for i, line in enumerate(self.lines, start=1):
            if line.strip().startswith(("|", "```")):
                continue
            if TEMPLATE_PLACEHOLDER_RE.search(line):
                found.append((i, line.strip()[:70]))
        return found


def section_lines(doc: Doc, name: str) -> list[tuple[int, str]] | None:
    """Lines under `## <name>`, up to the next `#`/`##` heading, as (1-based line, text).
    None when the section is absent -- distinct from present and empty."""
    out: list[tuple[int, str]] | None = None
    for i, line in enumerate(doc.lines, start=1):
        if out is None:
            if line.startswith("## ") and line[3:].strip() == name:
                out = []
            continue
        if line.startswith("## ") or line.startswith("# "):
            break
        out.append((i, line))
    return out


@dataclass
class Skip:
    step: str       # normalised: lower case, no backticks
    reason: str
    line: int       # 1-based


def skipped_steps(doc: Doc) -> tuple[list[Skip], list[tuple[int, str]]]:
    """Parse `## Skipped steps`: one bullet per skip, `- <step>: <reason>`.

    Returns (skips, unparsed). A bullet with no colon is a skip with an empty
    reason, so it is reported as unreasoned rather than dropped. "None." (with or
    without a bullet) and blank lines mean nothing. Any other non-bullet line is
    returned as unparsed: prose there is not a recorded skip."""
    skips: list[Skip] = []
    unparsed: list[tuple[int, str]] = []
    for line_no, raw in section_lines(doc, SKIP_SECTION) or []:
        text = raw.strip()
        if not text:
            continue
        bullet = text[:1] in ("-", "*")
        body = text[1:].strip() if bullet else text
        if body.rstrip(".").strip().lower() == "none":
            continue
        if not bullet:
            unparsed.append((line_no, text))
            continue
        step, _, reason = body.partition(":")
        skips.append(Skip(step.strip().strip("`*").strip().lower(), reason.strip(), line_no))
    return skips, unparsed


def reasoned_skips(doc: Doc) -> dict[str, str]:
    """{step: reason} for every known step listed with a reason long enough to count.
    This is what "the plan lists the step as skipped" means everywhere downstream."""
    skips, _ = skipped_steps(doc)
    return {s.step: s.reason for s in skips
            if s.step in SKIPPABLE_STEPS and len(s.reason) >= MIN_REASON}


def issue_number(doc: Doc) -> str:
    """The number from the frontmatter's `issue: owner/repo#123`, or ""."""
    issue = doc.frontmatter.get("issue", "")
    return issue.rpartition("#")[2] if ISSUE_RE.match(issue) else ""


def fingerprint(path: Path) -> str:
    """Stable hash of a file's content, used to detect a PRD changing under an
    acceptance file that was supposed to be frozen against it."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def requirement_ids(prd_path: Path) -> list[str]:
    doc = Doc(prd_path)
    return [b.id for b in doc.blocks(REQ_HEADING_RE, "## ")]


def check_frontmatter(doc: Doc, required: list[str], out: list[Finding]) -> None:
    if not doc.frontmatter:
        out.append(Finding(ERROR, "frontmatter.missing", 1,
                           "No YAML frontmatter found."))
        return
    for key in required:
        if not doc.frontmatter.get(key):
            out.append(Finding(ERROR, "frontmatter.field", 1,
                               f"Frontmatter is missing required field '{key}'."))
    issue = doc.frontmatter.get("issue", "")
    if issue and not ISSUE_RE.match(issue):
        out.append(Finding(ERROR, "frontmatter.issue", 1,
                           f"issue '{issue}' should look like 'owner/repo#123'."))
    created = doc.frontmatter.get("created", "")
    if created and not DATE_RE.match(created):
        out.append(Finding(ERROR, "frontmatter.created", 1,
                           f"created '{created}' should be an ISO date (YYYY-MM-DD)."))


def check_common(doc: Doc, out: list[Finding]) -> None:
    for line_no, text in doc.placeholders():
        out.append(Finding(ERROR, "template.leftover", line_no,
                           f"Unfilled template placeholder: {text!r}."))
    for line_no, detail in doc.needs_input():
        out.append(Finding(BLOCKED, "input.needed", line_no, detail))


def exit_code(findings: list[Finding]) -> int:
    if any(f.level == ERROR for f in findings):
        return 1
    if any(f.level == BLOCKED for f in findings):
        return 2
    return 0


def render(path: Path, findings: list[Finding], headline: str, quiet: bool = False) -> str:
    code = exit_code(findings)
    label = {0: "PASS", 1: "FAIL (structural)", 2: "BLOCKED (needs input)"}[code]
    lines = [f"{label}  {path}"]
    if headline:
        lines.append(f"  {headline}")
    for level, heading in ((ERROR, "errors"), (BLOCKED, "blocked on input"), (WARN, "warnings")):
        group = [f for f in findings if f.level == level]
        if not group or (quiet and level == WARN):
            continue
        lines.append(f"\n  {heading} ({len(group)}):")
        for f in sorted(group, key=lambda x: x.line):
            lines.append(f"    line {f.line:>4}  [{f.code}] {f.message}")
    return "\n".join(lines)
