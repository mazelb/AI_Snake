#!/usr/bin/env python3
"""
Structural validator for acceptance.md.

Two jobs beyond the usual structure checks:

1. Every case must cite a requirement that exists. Acceptance cases derived from
   the implementation rather than the PRD are the failure this whole stage exists
   to prevent, and a case citing no requirement is the visible symptom.

2. The freeze check. Acceptance is generated from the PRD before code exists and
   frozen against it. If the PRD changed afterwards, these cases may be verifying
   an intent nobody holds any more — that is a warning, not an error, because the
   right response is human judgement about which one moved.

Exit codes: 0 clean · 1 structural errors · 2 blocked on missing input
"""

from __future__ import annotations

import argparse
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
    ERROR, WARN, AC_HEADING_RE, MIN_REASON, REQ_HEADING_RE, REQ_ID_RE, Doc, Finding,
    check_common, check_frontmatter, exit_code, fingerprint, render, requirement_ids,
    section_lines,
)

REQUIRED_FRONTMATTER = ["title", "issue", "prd", "prd_fingerprint", "status", "created"]
REQUIRED_FIELDS = ["type", "given", "when", "then", "fails if"]
VALID_TYPES = {"automated", "manual"}

# Phrasing that describes code rather than intent. An acceptance case should be
# writable before the implementation exists; these words mean it wasn't.
IMPLEMENTATION_LEAK = [
    "the function", "the method", "the class", "the handler", "the component",
    "returns true", "returns false", "returns null", "the variable", "the constant",
    "calls the", "the helper", "is mocked", "the stub", "the private",
]


def withdrawn_ids(prd_path: Path) -> set[str]:
    """The PRD's requirements marked [WITHDRAWN], read as coverage.py reads them."""
    return {b.id for b in Doc(prd_path).blocks(REQ_HEADING_RE, "## ")
            if "[WITHDRAWN]" in b.body or "[WITHDRAWN]" in b.name}


def has_reason(line: str) -> bool:
    """True when a 'Not covered' line says more than the ids it names: at least
    MIN_REASON characters once the ids, the bullet and the punctuation around them
    are gone ('- REQ-003' and '- REQ-003: n/a' have none)."""
    rest = re.sub(r"[\s\-*:;,.()\[\]`—–]+", " ", REQ_ID_RE.sub(" ", line)).strip()
    return len(rest) >= MIN_REASON


def validate(path: Path) -> tuple[list[Finding], str]:
    doc = Doc(path)
    findings: list[Finding] = []
    check_frontmatter(doc, REQUIRED_FRONTMATTER, findings)
    check_common(doc, findings)

    prd_rel = doc.frontmatter.get("prd", "")
    known_reqs: list[str] = []
    withdrawn: set[str] = set()
    if prd_rel:
        prd_path = (path.parent / Path(prd_rel).name)
        if not prd_path.exists():
            prd_path = Path(prd_rel)
        if prd_path.exists():
            known_reqs = requirement_ids(prd_path)
            withdrawn = withdrawn_ids(prd_path)
            stored = doc.frontmatter.get("prd_fingerprint", "")
            current = fingerprint(prd_path)
            if stored and stored != current:
                findings.append(Finding(WARN, "freeze.stale", 1,
                                        f"PRD has changed since these cases were frozen "
                                        f"(recorded {stored}, now {current}). Decide which one "
                                        "moved before trusting a pass or a fail here."))
        else:
            findings.append(Finding(ERROR, "prd.missing", 1,
                                    f"PRD not found at '{prd_rel}'."))

    cases = doc.blocks(AC_HEADING_RE, "# ")
    if not cases:
        findings.append(Finding(ERROR, "ac.none", 1,
                                "No acceptance cases found. Expected '## AC-001 [REQ-001] name'."))

    seen: set[str] = set()
    verified: set[str] = set()
    automated = 0

    for idx, case in enumerate(cases, start=1):
        line_no = case.start + 1
        heading = doc.lines[case.start]
        req = AC_HEADING_RE.match(heading).group(2)
        verified.add(req)

        if case.id in seen:
            findings.append(Finding(ERROR, "ac.duplicate", line_no,
                                    f"{case.id} appears more than once."))
        seen.add(case.id)
        expected = f"AC-{idx:03d}"
        if case.id != expected:
            findings.append(Finding(WARN, "ac.sequence", line_no,
                                    f"{case.id} is at position {idx}, expected {expected}."))

        if known_reqs and req not in known_reqs:
            findings.append(Finding(ERROR, "ac.badref", line_no,
                                    f"{case.id} verifies {req}, which does not exist in the PRD."))

        fields = case.fields()
        for name in REQUIRED_FIELDS:
            if not fields.get(name):
                findings.append(Finding(ERROR, "ac.field", line_no,
                                        f"{case.id} is missing '{name.title()}:'."))

        ctype = fields.get("type", "").lower()
        if ctype and ctype not in VALID_TYPES:
            findings.append(Finding(ERROR, "ac.type", line_no,
                                    f"{case.id} type '{ctype}' is not automated or manual."))
        if ctype == "automated":
            automated += 1

        then = fields.get("then", "")
        if then and len(then) < 20:
            findings.append(Finding(ERROR, "ac.thinthen", line_no,
                                    f"{case.id} 'Then' is too short to be checkable: {then!r}."))

        fails_if = fields.get("fails if", "")
        if fails_if and fails_if.lower().strip(". ") in {"it does not", "the above fails", "not met"}:
            findings.append(Finding(WARN, "ac.circularfail", line_no,
                                    f"{case.id} 'Fails if' just negates 'Then'. Name the specific "
                                    "wrong behaviour this case is designed to catch."))

        body = case.body.lower()
        leaks = [t for t in IMPLEMENTATION_LEAK if t in body]
        if leaks:
            findings.append(Finding(WARN, "ac.implementationleak", line_no,
                                    f"{case.id} refers to {', '.join(repr(l) for l in leaks)} — "
                                    "that describes code, not intent. These cases must be writable "
                                    "before the implementation exists."))

    if "Not covered" not in {l[3:].strip() for l in doc.lines if l.startswith("## ")}:
        findings.append(Finding(WARN, "ac.nonotcovered", 1,
                                "No '## Not covered' section. An untested requirement nobody has "
                                "noticed is the failure mode this section exists to prevent."))

    # A requirement with no case is accounted for when the PRD withdraws it, or when
    # a line under 'Not covered' names it with a reason, as the error below says.
    # Without either, a withdrawn one could only pass with an invented case (M1).
    not_covered = section_lines(doc, "Not covered") or []
    for req in known_reqs:
        if req in verified or req in withdrawn:
            continue
        listed = [(n, text) for n, text in not_covered if re.search(rf"\b{req}\b", text)]
        if not listed:
            findings.append(Finding(ERROR, "req.unverified", 1,
                                    f"{req} has no acceptance case. Either write one or list it "
                                    "under 'Not covered' with a reason."))
        elif not any(has_reason(text) for _, text in listed):
            findings.append(Finding(ERROR, "req.notcoveredreason", listed[0][0],
                                    f"{req} is listed under 'Not covered' with no reason. Say on "
                                    f"its line why it has no case: '- {req}: <reason>'."))

    headline = (f"cases: {len(cases)} ({automated} automated) · "
                f"requirements verified: {len(verified)}/{len(known_reqs) or '?'}")
    return findings, headline


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate acceptance-case structure.")
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
