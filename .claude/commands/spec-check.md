---
description: Validate every spec artifact and show requirement coverage
argument-hint: [path-or-issue-number, default all]
allowed-tools: Bash(python3 *), Bash(bash *), Bash(ls *), Read
model: haiku
disable-model-invocation: true
---

<!--
  The choice between every spec, one file and one issue is made in
  spec-check-all.sh, not here, and the line ends in `| cat`: outside auto mode a
  preprocessing line holding an `if` is refused, and one that exits non-zero
  (any failing or blocked artifact) aborts the command; both silently, with an
  empty result (build item 29).
-->

!`bash .claude/skills/dev-flow/scripts/spec-check-all.sh "$ARGUMENTS" 2>&1 | cat`

Summarize in three lines or fewer: what passes, what is structurally broken, what
is blocked on a human, and any coverage gap.

BLOCKED (exit 2) is not a failure — it means a document is correct and waiting on
a number only a person can supply. Do not offer to fill those in.
