---
description: Implement an approved plan, task by task, without seeing the acceptance cases
argument-hint: <issue-number>
allowed-tools: Bash(python3 .claude/skills/dev-flow/scripts/coverage.py *), Bash(mkdir -p .dev-flow-run), Bash(rm -f .dev-flow-run/authoring-*), Bash(touch *), Read, Write, Edit, Grep, Glob
disable-model-invocation: true
---

<!--
  No bare `Bash` grant (DECISIONS.md DR1). The grants left are what the
  context lines below run: the coverage script, and the `mkdir`, `rm` and
  `touch` that set the implementing marker. The `cat` and `grep` lines are read-only
  commands and need none. Anything else you run in Bash (the project's tests,
  git) goes through the normal permission rules, so interactively it may prompt.

  The marker, .dev-flow-run/implementing-<issue>, tells the guard hooks an
  issue is being implemented: acceptance-guard.sh keeps that issue's cases
  locked even if a verifying- marker is lying around, and integrity-guard.sh
  protects flow.json, the lint and format configs and acceptance.md.
  /verify removes it. The same line removes any authoring-<issue> marker that
  /acceptance or /harness left behind (DECISIONS.md B8); the implementing
  marker would keep the issue locked anyway, but a stale unlock is not left
  lying around. That rm grant ends in `authoring-*`, not ` *`, since
  the argument placeholder is not filled in allowed-tools (build item 26).
-->

# Context

- Phase: !`mkdir -p .dev-flow-run && rm -f .dev-flow-run/authoring-$ARGUMENTS && touch .dev-flow-run/implementing-$ARGUMENTS && echo "implementing issue $ARGUMENTS: its acceptance cases stay locked, and flow.json, the lint and format configs and acceptance.md are protected, until /verify $ARGUMENTS"`
- Plan: !`cat specs/$ARGUMENTS-*/plan.md 2>/dev/null || echo "NO PLAN FOUND for issue $ARGUMENTS — run /plan $ARGUMENTS first"`
- Plan status: !`grep -h '^status:' specs/$ARGUMENTS-*/plan.md 2>/dev/null || echo "unknown"`
- Coverage: !`python3 .claude/skills/dev-flow/scripts/coverage.py specs/$ARGUMENTS-* 2>&1 | head -20`

# Task

Implement the plan for issue #$ARGUMENTS.

**Refuse if the plan is not approved.** `status:` must be `approved`. If it says
`draft`, stop and tell me — approving the plan is the one mandatory human gate in
this pipeline, and it exists precisely so that nothing expensive runs on a plan
nobody read.

**You cannot read `specs/*/acceptance.md`.** A hook blocks it, and that is
deliberate rather than a formality. Code written against visible tests passes those
tests; it does not necessarily satisfy the requirement they were derived from. If
you find yourself wanting to look, that is the signal the plan or the PRD is
ambiguous — ask me instead.

**Fix the code, not the checks.** Until `/verify $ARGUMENTS` runs, a second hook
blocks edits to `flow.json`, the lint and format configs and `acceptance.md`, and
blocks `--no-verify` and `core.hooksPath`. If a check is wrong, stop and tell me.

Work task by task, in the sequencing order the plan gives:

1. Read the requirement the task cites in the PRD. Implement against that. If the
   plan lists the PRD under `## Skipped steps`, the task cites the issue instead
   (`Satisfies: #$ARGUMENTS`); implement against the task and the plan's approach.
2. Write your own tests as you go. `/tdd` is available and is the better path when
   the task suits it: test at the seams the task's `Seams:` line names. My approving
   the plan confirmed those seams, so do not stop to ask about them again. A task
   with `Seams: none — <reason>` has nothing to test at. Your tests are not the
   acceptance cases and do not replace them.
3. Commit per task, with the task and requirement ids in the message:
   `TASK-003: persist session state (REQ-002)`. With the PRD skipped, cite the task
   and the issue: `TASK-001: fix the retry off-by-one (#$ARGUMENTS)`.
4. If a task turns out to be wrong or impossible, stop and say so. Do not
   improvise a different approach — that silently invalidates the plan I approved.

When every task is done, run the repo's own test suite and report. Then stop.
Verification is `/verify $ARGUMENTS`, and it is a separate step for the same reason the
acceptance cases are hidden.
