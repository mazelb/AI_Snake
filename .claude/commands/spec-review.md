---
description: Advisory review of a PRD — validator output plus the judgment a script cannot do
argument-hint: <path-or-issue-number>
allowed-tools: Bash(python3 *), Bash(ls *), Read, Grep, Glob
---

Validator output:

!`V=.claude/skills/dev-flow/scripts/validate_prd.py; if [ -f "$ARGUMENTS" ]; then python3 $V "$ARGUMENTS"; else python3 $V specs/$ARGUMENTS-*/prd.md; fi 2>&1`

Read the PRD itself, then review it.

Lead with the validator findings above — they are objective and cost nothing to
state. Then add the layer the script cannot reach:

- Is the success metric the one that reflects the problem, or the one that was
  easy to measure?
- Do the requirements collectively deliver the stated outcome, or is there a gap
  between them that nobody has noticed?
- What does this assume without saying — about traffic, permissions, upstream
  availability, or capacity?
- Which requirements are load-bearing for the outcome, and which are incidental?

This is advisory. Do not edit the file, and do not present your judgment as a
gate — the only gate in this pipeline is the validator and the human reading it.
