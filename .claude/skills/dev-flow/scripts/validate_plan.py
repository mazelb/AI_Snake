#!/usr/bin/env python3
"""
Structural validator for plan.md.

The plan is the last cheap checkpoint before compute starts spending, so what
this checks is traceability rather than quality: every task points at a real
requirement, every task has a done-condition and names its test seams, and no
task exists that no requirement asked for. That last one is scope creep, and the
plan stage is where it enters a pipeline most easily and most quietly.

Skipped steps. A plan may list steps it skips under `## Skipped steps`, one
`- <step>: <reason>` line each; approving the plan approves the skips (Q5). Only
`prd` and `acceptance` are skippable (build C6). A skip with no reason, or of any
other step, is an error. When the PRD is skipped, tasks cite the issue instead --
`Satisfies: #42`, the plan's own issue -- and the PRD checks do not apply. A task
citing `#N` in a plan that does not skip the PRD is an error.

Seams. Every task has a `Seams:` line naming where its tests attach, or
`Seams: none — <reason>` (build C6; Q1). `/tdd` must confirm seams with a person,
and approving the plan is that confirmation.

Touches. `Touches:` is a warning when missing, and an error when `flow.json` has
`unattended.enabled: true`: an unattended run holds each task to its `Touches:`,
so a task without one has no scope to hold it to.

Exit codes: 0 clean · 1 structural errors · 2 blocked on missing input
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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from spec_lib import (  # noqa: E402
    ERROR, WARN, Doc, Finding, ISSUE_REF_RE, MIN_REASON, REQ_ID_RE, SKIP_SECTION,
    SKIPPABLE_STEPS, TASK_HEADING_RE,
    check_common, check_frontmatter, exit_code, issue_number, reasoned_skips, render,
    requirement_ids, skipped_steps,
)

REQUIRED_FRONTMATTER = ["title", "issue", "prd", "owner", "status", "created"]
REQUIRED_SECTIONS = ["Approach", "Tasks", "Sequencing", "Out of scope"]

# Same names pipeline_config.py looks for, in the same order, from the working
# directory -- where every command and hook runs.
CONFIG_NAMES = ["flow.json", ".flow.json", ".claude/flow.json"]

SEAMS_NONE_RE = re.compile(r"^none\b[\s—–:,;.\-]*(.*)$", re.IGNORECASE)


def unattended_enabled(findings: list[Finding]) -> bool:
    """True when flow.json sets `unattended.enabled: true`. A flow.json that does
    not parse is an error: whether this plan runs unattended cannot be told."""
    for name in CONFIG_NAMES:
        candidate = Path(name)
        if not candidate.exists():
            continue
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            findings.append(Finding(ERROR, "flow.invalid", 1,
                                    f"{candidate} does not parse ({exc}), so whether this "
                                    "plan runs unattended cannot be told."))
            return False
        block = data.get("unattended") if isinstance(data, dict) else None
        return isinstance(block, dict) and block.get("enabled") is True
    return False


def check_skips(doc: Doc, findings: list[Finding]) -> None:
    skips, unparsed = skipped_steps(doc)
    seen: set[str] = set()
    for skip in skips:
        if skip.step not in SKIPPABLE_STEPS:
            findings.append(Finding(ERROR, "skip.unknown", skip.line,
                                    f"'{skip.step}' is not a step that can be skipped. "
                                    f"Skippable: {', '.join(SKIPPABLE_STEPS)}."))
            continue
        if len(skip.reason) < MIN_REASON:
            findings.append(Finding(ERROR, "skip.noreason", skip.line,
                                    f"Skipping '{skip.step}' needs a reason, as "
                                    f"'- {skip.step}: <why>'. Approving the plan approves "
                                    "the skip, so the reason is what gets approved."))
        if skip.step in seen:
            findings.append(Finding(WARN, "skip.duplicate", skip.line,
                                    f"'{skip.step}' is listed as skipped more than once."))
        seen.add(skip.step)
    for line_no, text in unparsed:
        findings.append(Finding(WARN, "skip.unparsed", line_no,
                                f"Not read as a skip: {text[:60]!r}. A skip is a bullet, "
                                "'- <step>: <reason>'; write 'None.' when nothing is skipped."))


def validate(path: Path) -> tuple[list[Finding], str]:
    doc = Doc(path)
    findings: list[Finding] = []
    skipped = reasoned_skips(doc)
    prd_skipped = "prd" in skipped

    required = [k for k in REQUIRED_FRONTMATTER if not (prd_skipped and k == "prd")]
    check_frontmatter(doc, required, findings)
    check_common(doc, findings)

    headings = {l[3:].strip() for l in doc.lines if l.startswith("## ")}
    for name in REQUIRED_SECTIONS:
        if name not in headings:
            findings.append(Finding(ERROR, "section.missing", 1,
                                    f"Required section '## {name}' is missing."))
    if SKIP_SECTION in headings:
        check_skips(doc, findings)

    # Resolve the PRD this plan claims to implement -- unless the plan skips it.
    prd_rel = doc.frontmatter.get("prd", "")
    known_reqs: list[str] = []
    prd_path = None
    if prd_rel and prd_rel.lower() != "none":
        prd_path = (path.parent / Path(prd_rel).name)
        if not prd_path.exists():
            prd_path = Path(prd_rel)
        if not prd_path.exists():
            prd_path = None
    if prd_skipped:
        if prd_path is not None or (path.parent / "prd.md").exists():
            findings.append(Finding(ERROR, "prd.skipconflict", 1,
                                    "The plan lists the PRD as skipped, but a PRD exists "
                                    "for it. Cite its requirements and drop the skip, or "
                                    "set 'prd: none'."))
    elif prd_path is not None:
        known_reqs = requirement_ids(prd_path)
        if not known_reqs:
            findings.append(Finding(ERROR, "prd.noreqs", 1,
                                    f"PRD at {prd_path} declares no requirements."))
    elif prd_rel.lower() == "none":
        findings.append(Finding(ERROR, "prd.missing", 1,
                                "The plan says 'prd: none', but '## Skipped steps' does not "
                                "list the PRD with a reason. A plan with no PRD behind it "
                                "is accepted only with that skip recorded."))
    elif prd_rel:
        findings.append(Finding(ERROR, "prd.missing", 1,
                                f"PRD not found at '{prd_rel}'. A plan with no PRD "
                                "behind it has nothing to be traceable to, unless "
                                f"'## {SKIP_SECTION}' lists the PRD with a reason."))

    own_issue = issue_number(doc)
    unattended = unattended_enabled(findings)

    tasks = doc.blocks(TASK_HEADING_RE, "## ")
    if not tasks:
        findings.append(Finding(ERROR, "task.none", 1,
                                "No tasks found. Expected '### TASK-001 short name'."))

    seen: set[str] = set()
    cited: set[str] = set()
    for idx, task in enumerate(tasks, start=1):
        line_no = task.start + 1
        if task.id in seen:
            findings.append(Finding(ERROR, "task.duplicate", line_no,
                                    f"{task.id} appears more than once."))
        seen.add(task.id)
        expected = f"TASK-{idx:03d}"
        if task.id != expected:
            findings.append(Finding(WARN, "task.sequence", line_no,
                                    f"{task.id} is at position {idx}, expected {expected}."))

        fields = task.fields()

        satisfies = fields.get("satisfies", "")
        refs = REQ_ID_RE.findall(satisfies)
        issue_refs = ISSUE_REF_RE.findall(satisfies)
        if prd_skipped:
            if not refs and not issue_refs:
                findings.append(Finding(ERROR, "task.nosatisfies", line_no,
                                        f"{task.id} has no 'Satisfies: #{own_issue or 'N'}' "
                                        "line. With the PRD skipped, a task cites the issue; "
                                        "one that cites nothing is work nobody asked for."))
            for ref in refs:
                findings.append(Finding(ERROR, "task.badref", line_no,
                                        f"{task.id} cites {ref}, but the plan skips the PRD, "
                                        "so there are no requirements to cite. Cite the issue."))
            for num in issue_refs:
                cited.add(f"#{num}")
                if own_issue and num != own_issue:
                    findings.append(Finding(ERROR, "task.badissue", line_no,
                                            f"{task.id} cites #{num}; this plan is for "
                                            f"#{own_issue}."))
        else:
            if not refs and not issue_refs:
                findings.append(Finding(ERROR, "task.nosatisfies", line_no,
                                        f"{task.id} has no 'Satisfies: REQ-00x' line. A task "
                                        "that satisfies no requirement is work nobody asked for."))
            for num in issue_refs:
                findings.append(Finding(ERROR, "task.issueref", line_no,
                                        f"{task.id} cites #{num}. Citing the issue is accepted "
                                        f"only when '## {SKIP_SECTION}' lists the PRD with a "
                                        "reason; otherwise cite the requirement."))
            for ref in refs:
                cited.add(ref)
                if known_reqs and ref not in known_reqs:
                    findings.append(Finding(ERROR, "task.badref", line_no,
                                            f"{task.id} cites {ref}, which does not exist in the PRD."))

        if not fields.get("touches"):
            if unattended:
                findings.append(Finding(ERROR, "task.notouches", line_no,
                                        f"{task.id} does not say what it touches. flow.json has "
                                        "unattended.enabled, and an unattended run holds each "
                                        "task to its 'Touches:' -- without one there is no scope."))
            else:
                findings.append(Finding(WARN, "task.notouches", line_no,
                                        f"{task.id} does not say what it touches. Naming the modules "
                                        "up front is what makes a plan reviewable in three minutes."))

        seams = fields.get("seams", "")
        if not seams:
            findings.append(Finding(ERROR, "task.noseams", line_no,
                                    f"{task.id} has no 'Seams:' line. Name where its tests attach, "
                                    "or write 'Seams: none — <reason>'. Approving the plan is "
                                    "what confirms the seams /tdd tests at."))
        else:
            m = SEAMS_NONE_RE.match(seams)
            if m and len(m.group(1).strip()) < MIN_REASON:
                findings.append(Finding(ERROR, "task.seamsnoreason", line_no,
                                        f"{task.id} says 'Seams: none' without a reason. Write "
                                        "'Seams: none — <why this task has nothing to test at>'."))

        done = fields.get("done when", "")
        if not done:
            findings.append(Finding(ERROR, "task.nodone", line_no,
                                    f"{task.id} has no 'Done when:' condition."))
        elif len(done) < 15:
            findings.append(Finding(ERROR, "task.thindone", line_no,
                                    f"{task.id} done-condition is too short to be checkable: {done!r}."))

        prose = "\n".join(l for l in task.lines if not l.strip().startswith(("-", "*"))).strip()
        if len(prose) < 15:
            findings.append(Finding(WARN, "task.nodescription", line_no,
                                    f"{task.id} has no description beyond its fields."))

    # Requirements with no task are reported here as a warning; coverage.py is the
    # tool that treats it as a failure, once acceptance exists too.
    for req in known_reqs:
        if req not in cited:
            findings.append(Finding(WARN, "req.uncovered", 1,
                                    f"{req} is not satisfied by any task. Intentional deferral "
                                    "is fine — say so in 'Out of scope'."))

    if prd_skipped:
        headline = (f"tasks: {len(tasks)} · no PRD — issue-cited "
                    f"(#{own_issue or '?'}) · skipped: {', '.join(skipped)}")
    else:
        headline = f"tasks: {len(tasks)} · requirements cited: {len(cited)}/{len(known_reqs) or '?'}"
        if skipped:
            headline += f" · skipped: {', '.join(skipped)}"
    if unattended:
        headline += " · unattended"
    return findings, headline


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate plan structure.")
    ap.add_argument("paths", nargs="+", type=Path)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    worst = 0
    for path in args.paths:
        if not path.exists():
            print(f"FAIL  {path}: file not found", file=sys.stderr)
            worst = max(worst, 1)
            continue
        findings, headline = validate(path)
        worst = max(worst, exit_code(findings))
        print(render(path, findings, headline, args.quiet))
        print()
    return worst


if __name__ == "__main__":
    sys.exit(main())
