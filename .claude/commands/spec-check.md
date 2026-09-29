---
description: Validate every spec artifact and show requirement coverage
argument-hint: [path-or-issue-number, default all]
allowed-tools: Bash(python3 *), Bash(bash *), Bash(ls *), Read
model: haiku
disable-model-invocation: true
---

!`S=.claude/skills/dev-flow/scripts; if [ -z "$ARGUMENTS" ]; then bash $S/spec-check-all.sh; elif [ -f "$ARGUMENTS" ]; then case "$ARGUMENTS" in *prd.md) python3 $S/validate_prd.py "$ARGUMENTS";; *plan.md) python3 $S/validate_plan.py "$ARGUMENTS";; *acceptance.md) python3 $S/validate_acceptance.py "$ARGUMENTS";; esac; else for f in specs/$ARGUMENTS-*/prd.md specs/$ARGUMENTS-*/plan.md specs/$ARGUMENTS-*/acceptance.md; do [ -f "$f" ] || continue; case "$f" in *prd.md) python3 $S/validate_prd.py "$f";; *plan.md) python3 $S/validate_plan.py "$f";; *acceptance.md) python3 $S/validate_acceptance.py "$f";; esac; done; python3 $S/coverage.py specs/$ARGUMENTS-*; fi 2>&1`

Summarize in three lines or fewer: what passes, what is structurally broken, what
is blocked on a human, and any coverage gap.

Exit 2 is not a failure — it means a document is correct and waiting on a number
only a person can supply. Do not offer to fill those in.
