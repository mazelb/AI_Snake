---
description: Derive frozen acceptance cases from a PRD, in a forked context
argument-hint: <issue-number>
allowed-tools: Bash(python3 .claude/skills/dev-flow/scripts/validate_prd.py *), Bash(python3 .claude/skills/dev-flow/scripts/validate_acceptance.py *), Bash(ls *), Bash(echo *), Bash(mkdir -p .dev-flow-run), Bash(touch .dev-flow-run/authoring-*), Bash(rm -f .dev-flow-run/authoring-*), Read, Edit(specs/**)
context: fork
disable-model-invocation: true
---

<!--
  The fingerprint used to be computed by a `python3 -c` one-liner, which needed
  a grant allowing arbitrary Python — in the headless job, the single most
  useful capability an injected instruction could ask for. It is now a
  `--fingerprint` flag on the validator that already exists, so the grant can
  name one script instead of an interpreter.

  The `cat specs/...` line needs no grant: `cat` is in Claude Code's read-only
  command set. The `cat specs/` grant this file used to carry never matched it:
  a trailing `:*` means ` *`, so it needed a space after the slash (measured in
  build item 5).

  The Stage line sets .dev-flow-run/authoring-<issue> (DECISIONS.md B8). Without
  it acceptance-guard.sh blocks the validator run below, since the command names
  acceptance.md; with it, this issue's cases are readable, and still writable,
  until the rm at the end. It is a preprocessing line, so no hook sees it, and
  the guard blocks any tool call that tries to create such a marker. The three
  marker grants end in `authoring-*` rather than the ` *` form every other rule
  uses: the argument placeholder is not filled in allowed-tools, and `Bash(rm -f *)`
  would let this stage delete any file unprompted (measured in build item 26).
-->

# Context

- Stage: !`mkdir -p .dev-flow-run && touch .dev-flow-run/authoring-$ARGUMENTS && echo "writing the acceptance cases for issue $ARGUMENTS"`
- PRD: !`cat specs/$ARGUMENTS-*/prd.md 2>/dev/null || echo "NO PRD FOUND for issue $ARGUMENTS"`
- PRD fingerprint: !`python3 .claude/skills/dev-flow/scripts/validate_prd.py --fingerprint specs/$ARGUMENTS-*/prd.md 2>/dev/null || echo UNKNOWN`

# Task

Derive acceptance cases for issue #$ARGUMENTS from **the PRD above and nothing else**.

You are running in a forked context on purpose. Do not read the implementation,
the plan, or the existing tests — not to find naming conventions, not for
context, not to check what is feasible. Cases derived from code verify what the
code does; cases derived from the PRD verify what was asked for. Only the second
kind can fail usefully.

Write `specs/$ARGUMENTS-<slug>/acceptance.md` from
`.claude/skills/dev-flow/assets/acceptance-template.md`.

- One or more cases per requirement. Every case cites its `REQ-` id in the heading.
- `Then` states the observable outcome with its number or exact state.
- `Fails if` names the specific wrong behaviour the case is designed to catch —
  not a negation of `Then`. This field is what makes a case worth writing.
- Set `prd_fingerprint` to the value shown above. That freezes these cases against
  this version of the PRD.
- Any requirement you cannot verify goes under `## Not covered` with the reason,
  usually missing infrastructure. Naming the hole is the job; a requirement that
  is quietly untested is the failure this stage exists to prevent.

Then run
`python3 .claude/skills/dev-flow/scripts/validate_acceptance.py specs/$ARGUMENTS-*/acceptance.md`
and fix structural errors.

Your last command, after everything else and whatever the outcome, is
`rm -f .dev-flow-run/authoring-$ARGUMENTS`, as a command of its own. It locks the
cases again: after it, nothing in this session can read them, so run nothing
that names them afterwards.

These cases are frozen once written. The coding agent will not be allowed to read
them.
