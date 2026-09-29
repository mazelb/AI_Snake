---
description: Turn a validated PRD into an implementation plan with traceable tasks
argument-hint: <issue-number>
allowed-tools: Bash(python3 .claude/skills/dev-flow/scripts/validate_prd.py *), Bash(python3 .claude/skills/dev-flow/scripts/validate_plan.py *), Bash(python3 .claude/skills/dev-flow/scripts/coverage.py *), Bash(head *), Bash(ls *), Bash(echo *), Read, Edit(specs/**), Grep, Glob
disable-model-invocation: true
---

<!--
  Each Bash grant above names the exact script it allows. The broad
  `python3` grant this command used to carry allowed any Python at all, which
  in the headless job meant any code the issue text could talk the model into
  running. The commands below are unchanged; only what is permitted is.

  The `cat specs/...` line needs no grant: `cat` is in Claude Code's read-only
  command set. The `cat specs/` grant this file used to carry never matched it:
  a trailing `:*` means ` *`, so it needed a space after the slash (measured in
  build item 5).
-->

# Context

- PRD: !`cat specs/$ARGUMENTS-*/prd.md 2>/dev/null || echo "NO PRD FOUND for issue $ARGUMENTS — run /spec $ARGUMENTS first"`
- PRD validator: !`python3 .claude/skills/dev-flow/scripts/validate_prd.py specs/$ARGUMENTS-*/prd.md 2>&1 | head -20`

# Task

Write the implementation plan for issue #$ARGUMENTS at `specs/$ARGUMENTS-<slug>/plan.md`, using
`.claude/skills/dev-flow/assets/plan-template.md`.

**Stop if the PRD is not ready.** If the validator above reports structural errors,
fix the PRD first. If it reports blocked items, tell me which ones and ask whether
to proceed — some blocked numbers do not affect decomposition, others make the plan
guesswork, and that judgement is mine to make.

**Decompose, do not restate.** A requirement says what must be true; a task says
what to do. If a task reads like its requirement with different verbs, the
decomposition has not happened yet.

Every task cites the requirements it satisfies. If you find yourself writing a task
that satisfies nothing in the PRD, that is scope entering the pipeline — do not
write it. Raise it to me as a question, or put it under "Out of scope".

Ground every task in real paths. Read the repo. `Touches:` should name files that
exist, or say plainly that a file is new. When `flow.json` has
`unattended.enabled`, a task without `Touches:` fails validation: an unattended
run holds each task to it.

**Name the seams on every task.** `Seams:` says where the task's tests attach — a
function, an endpoint, a module boundary — so `/tdd` can test there. When a task
has nothing to test at (config, docs), write `Seams: none — <why>`. My approving
the plan is what confirms the seams; nobody is asked again during implementation.

**Skipped steps.** List any step this work skips under `## Skipped steps`, one
`- <step>: <reason>` line each, or write "None.". Only `prd` and `acceptance` can
be skipped. You propose a skip; my approving the plan approves it.

**No PRD.** If the context above says there is no PRD, stop and tell me — unless
the work is the kind `SKILL.md` rule 1b says should not be specced (a one-liner, a
bug fix with an obvious cause). Then you may propose skipping it: list
`- prd: <reason>` under `## Skipped steps`, set `prd: none`, and have every task
cite the issue, `Satisfies: #$ARGUMENTS`. There are then no acceptance cases. You
cannot read the issue from here, so work from what I give you; ask me for the
issue text rather than guessing what it says.

Then run:

```
python3 .claude/skills/dev-flow/scripts/validate_plan.py specs/$ARGUMENTS-*/plan.md
python3 .claude/skills/dev-flow/scripts/coverage.py specs/$ARGUMENTS-*
```

Fix structural errors. Report the coverage table to me as-is.

**Then stop.** The plan is the human gate in this pipeline — I read it before any
implementation runs. Do not proceed to `/acceptance` or `/implement` on your own.
