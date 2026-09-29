---
description: Requirement coverage across prd, plan and acceptance
argument-hint: [issue-number, default all]
allowed-tools: Bash(python3 *), Read
model: haiku
disable-model-invocation: true
---

!`if [ -z "$ARGUMENTS" ]; then python3 .claude/skills/dev-flow/scripts/coverage.py; else python3 .claude/skills/dev-flow/scripts/coverage.py specs/$ARGUMENTS-*; fi 2>&1`

Summarize in three lines or fewer. Call out any requirement with no plan or no
test, and any task that satisfies no requirement — that last one is scope creep
and is worth naming directly rather than listing among the rest.
