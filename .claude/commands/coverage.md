---
description: Requirement coverage across prd, plan and acceptance
argument-hint: [issue-number, default all]
allowed-tools: Bash(python3 *), Read
model: haiku
disable-model-invocation: true
---

<!--
  No `if` in the line below, and it ends in `| cat`: outside auto mode a
  preprocessing line holding an `if` is refused, and one that exits non-zero
  (coverage.py exits 1 on a gap) aborts the command; both silently, with an empty
  result (build item 29). Each half runs only when its `test` fails: every spec
  with no argument, the issue's with one.
-->

!`test -n "$ARGUMENTS" || python3 .claude/skills/dev-flow/scripts/coverage.py 2>&1 | cat; test -z "$ARGUMENTS" || python3 .claude/skills/dev-flow/scripts/coverage.py specs/$ARGUMENTS-* 2>&1 | cat`

Summarize in three lines or fewer. Call out any requirement with no plan or no
test, and any task that satisfies no requirement — that last one is scope creep
and is worth naming directly rather than listing among the rest.
