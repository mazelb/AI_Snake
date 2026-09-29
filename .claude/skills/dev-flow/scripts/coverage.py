#!/usr/bin/env python3
"""
Requirement coverage across the three artifacts of a spec.

This is the payoff for requirement IDs. Once every task cites the requirement it
satisfies and every acceptance case cites the requirement it verifies, three
questions that normally need a meeting become a script:

  - which requirements have no plan?          (unimplemented intent)
  - which requirements have no test?          (unverified intent)
  - which tasks satisfy no requirement?       (scope creep)

A plan may skip the PRD (build C6): it lists `prd` under `## Skipped steps`
with a reason, and its tasks cite the issue, `Satisfies: #42`. Such a spec is
reported as "no PRD — issue-cited", not as missing. A task citing nothing, or
another issue, is still scope creep. There are no acceptance cases for it,
because they derive from the PRD.

Exit codes: 0 fully covered · 1 gaps found · 3 artifacts missing · 4 no specs yet

3 means a spec exists but is broken: its directory has no prd.md (and no plan
that skips the PRD), or the PRD declares no requirements. 4 means there is
nothing to check at all -- no directories under specs/ -- which is the normal
state of a new project, so a gate can let it through without also letting a
broken spec through.
"""

from __future__ import annotations

import argparse
import json
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
    AC_HEADING_RE, Doc, ISSUE_REF_RE, REQ_HEADING_RE, REQ_ID_RE, TASK_HEADING_RE,
    issue_number, reasoned_skips,
)


def collect(spec_dir: Path) -> dict:
    prd = spec_dir / "prd.md"
    plan = spec_dir / "plan.md"
    acceptance = spec_dir / "acceptance.md"
    delivery = spec_dir / "delivery.md"

    result = {
        "spec": str(spec_dir),
        "has_prd": prd.exists(),
        "has_plan": plan.exists(),
        "has_acceptance": acceptance.exists(),
        "has_delivery": delivery.exists(),
        "delivery_status": "",
        "outcome_verdict": "",
        "requirements": {},
        "orphan_tasks": [],
        "orphan_cases": [],
        "withdrawn": [],
        "skipped": {},
        "prd_skipped": False,
        "issue": "",
        "issue_tasks": [],
    }
    if delivery.exists():
        d = Doc(delivery)
        result["delivery_status"] = d.frontmatter.get("status", "")
        for raw in d.lines:
            s = raw.strip().lstrip("-* ")
            if s.lower().startswith("verdict:"):
                result["outcome_verdict"] = s.split(":", 1)[1].strip()
                break

    if plan.exists():
        plan_doc = Doc(plan)
        result["skipped"] = reasoned_skips(plan_doc)
        result["issue"] = issue_number(plan_doc)

    if not prd.exists():
        if plan.exists() and "prd" in result["skipped"]:
            result["prd_skipped"] = True
            collect_issue_cited(result, plan_doc)
            if acceptance.exists():
                doc = Doc(acceptance)
                for case in doc.blocks(AC_HEADING_RE, "# "):
                    result["orphan_cases"].append(
                        {"id": case.id, "reason": "the plan skips the PRD, so no requirement exists"})
        return result

    prd_doc = Doc(prd)
    for block in prd_doc.blocks(REQ_HEADING_RE, "## "):
        withdrawn = "[WITHDRAWN]" in block.body or "[WITHDRAWN]" in block.name
        result["requirements"][block.id] = {
            "name": block.name.replace("[WITHDRAWN]", "").strip(),
            "tasks": [],
            "cases": [],
            "withdrawn": withdrawn,
        }
        if withdrawn:
            result["withdrawn"].append(block.id)

    if plan.exists():
        for task in plan_doc.blocks(TASK_HEADING_RE, "## "):
            satisfies = task.fields().get("satisfies", "")
            refs = REQ_ID_RE.findall(satisfies)
            if not refs:
                nums = ISSUE_REF_RE.findall(satisfies)
                reason = (f"cites #{nums[0]}, but the plan does not skip the PRD" if nums
                          else "no Satisfies line")
                result["orphan_tasks"].append({"id": task.id, "reason": reason})
                continue
            for ref in refs:
                if ref in result["requirements"]:
                    result["requirements"][ref]["tasks"].append(task.id)
                else:
                    result["orphan_tasks"].append({"id": task.id, "reason": f"cites unknown {ref}"})

    if acceptance.exists():
        doc = Doc(acceptance)
        for case in doc.blocks(AC_HEADING_RE, "# "):
            ref = AC_HEADING_RE.match(doc.lines[case.start]).group(2)
            if ref in result["requirements"]:
                result["requirements"][ref]["cases"].append(case.id)
            else:
                result["orphan_cases"].append({"id": case.id, "reason": f"cites unknown {ref}"})

    return result


def collect_issue_cited(result: dict, plan_doc: Doc) -> None:
    """Tasks of a plan that skips the PRD: each should cite the plan's own issue."""
    own = result["issue"]
    for task in plan_doc.blocks(TASK_HEADING_RE, "## "):
        satisfies = task.fields().get("satisfies", "")
        nums = ISSUE_REF_RE.findall(satisfies)
        reqs = REQ_ID_RE.findall(satisfies)
        if reqs:
            result["orphan_tasks"].append(
                {"id": task.id, "reason": f"cites {reqs[0]}, but the plan skips the PRD"})
        elif not nums:
            result["orphan_tasks"].append({"id": task.id, "reason": "no Satisfies line"})
        elif own and any(n != own for n in nums):
            other = next(n for n in nums if n != own)
            result["orphan_tasks"].append(
                {"id": task.id, "reason": f"cites #{other}, not #{own}"})
        else:
            result["issue_tasks"].append(task.id)


def render_issue_cited(result: dict) -> tuple[str, int]:
    stage = ["plan"]
    if result["has_acceptance"]:
        stage.append("acceptance")
    if result["has_delivery"]:
        label = result["delivery_status"] or "delivery"
        if result["outcome_verdict"]:
            label += f"/{result['outcome_verdict']}"
        stage.append(label)
    header = f"{result['spec']}  [{' + '.join(stage)}]  no PRD — issue-cited"
    tasks = ",".join(t.replace("TASK-", "") for t in result["issue_tasks"]) or "—"
    lines = [header,
             f"  #{result['issue'] or '?'}  plan:{tasks}",
             f"  PRD skipped: {result['skipped']['prd']}"]
    gaps = 0
    if not result["issue_tasks"]:
        lines.append("  NO-PLAN  no task cites the issue")
        gaps += 1
    for orphan in result["orphan_tasks"]:
        lines.append(f"  SCOPE  {orphan['id']} satisfies nothing this plan is for ({orphan['reason']})")
        gaps += 1
    for orphan in result["orphan_cases"]:
        lines.append(f"  ORPHAN {orphan['id']} verifies no requirement ({orphan['reason']})")
        gaps += 1
    lines.append("  (no acceptance cases — they derive from the PRD, which was skipped)")
    lines.append(f"  → {'covered' if gaps == 0 else f'{gaps} gap(s)'}")
    return "\n".join(lines), (1 if gaps else 0)


def render(result: dict) -> tuple[str, int]:
    if result["prd_skipped"]:
        return render_issue_cited(result)
    if not result["has_prd"]:
        return f"MISSING  {result['spec']}: no prd.md", 3

    reqs = result["requirements"]
    if not reqs:
        return f"MISSING  {result['spec']}: prd.md declares no requirements", 3

    width = max(len(v["name"]) for v in reqs.values())
    width = min(max(width, 12), 44)

    rows = []
    gaps = 0
    for rid, info in reqs.items():
        if info["withdrawn"]:
            rows.append(f"  {rid}  {info['name'][:width]:<{width}}  withdrawn")
            continue
        plan_mark = ",".join(t.replace("TASK-", "") for t in info["tasks"]) or "—"
        case_mark = ",".join(c.replace("AC-", "") for c in info["cases"]) or "—"
        flag = ""
        if result["has_plan"] and not info["tasks"]:
            flag += " NO-PLAN"
            gaps += 1
        if result["has_acceptance"] and not info["cases"]:
            flag += " NO-TEST"
            gaps += 1
        rows.append(f"  {rid}  {info['name'][:width]:<{width}}  plan:{plan_mark:<10} test:{case_mark:<10}{flag}")

    stage = []
    stage.append("prd")
    if result["has_plan"]:
        stage.append("plan")
    if result["has_acceptance"]:
        stage.append("acceptance")
    elif "acceptance" in result["skipped"]:
        stage.append("acceptance skipped")
    if result["has_delivery"]:
        label = result["delivery_status"] or "delivery"
        if result["outcome_verdict"]:
            label += f"/{result['outcome_verdict']}"
        stage.append(label)

    header = f"{result['spec']}  [{' + '.join(stage)}]  {len(reqs)} requirements"
    lines = [header, *rows]

    for orphan in result["orphan_tasks"]:
        lines.append(f"  SCOPE  {orphan['id']} satisfies no requirement ({orphan['reason']})")
        gaps += 1
    for orphan in result["orphan_cases"]:
        lines.append(f"  ORPHAN {orphan['id']} verifies no requirement ({orphan['reason']})")
        gaps += 1

    if not result["has_plan"]:
        lines.append("  (no plan.md yet — plan coverage not evaluated)")
    if not result["has_acceptance"]:
        if "acceptance" in result["skipped"]:
            lines.append(f"  (acceptance skipped by the plan: {result['skipped']['acceptance']})")
        else:
            lines.append("  (no acceptance.md yet — test coverage not evaluated)")
    if result["delivery_status"] == "deployed" and not result["outcome_verdict"]:
        lines.append("  (deployed, outcome not yet measured — run /outcome)")
    elif result["has_acceptance"] and not result["has_delivery"]:
        lines.append("  (verified but not recorded as shipped — delivery is project-specific)")

    lines.append(f"  → {'covered' if gaps == 0 else f'{gaps} gap(s)'}")
    return "\n".join(lines), (1 if gaps else 0)


def main() -> int:
    ap = argparse.ArgumentParser(description="Requirement coverage across spec artifacts.")
    ap.add_argument("dirs", nargs="*", type=Path,
                    help="spec directories; defaults to every directory under specs/")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    args = ap.parse_args()

    dirs = args.dirs or sorted(p for p in Path("specs").glob("*") if p.is_dir())
    if not dirs:
        print("No spec directories found.", file=sys.stderr)
        return 4

    worst = 0
    payload = []
    for d in dirs:
        result = collect(d)
        if args.format == "json":
            payload.append(result)
            worst = max(worst, render(result)[1])
        else:
            text, code = render(result)
            worst = max(worst, code)
            print(text)
            print()

    if args.format == "json":
        print(json.dumps(payload, indent=2))
    return worst


if __name__ == "__main__":
    sys.exit(main())
