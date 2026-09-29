---
description: Run the frozen acceptance cases against the implementation and route failures
argument-hint: <issue-number>
allowed-tools: Bash, Read, Grep, Glob, Write, Edit
disable-model-invocation: true
---

<!--
  The unlock marker lives in .dev-flow-run/, not .claude/: Claude Code refuses
  agent writes into .claude/ by every route, so a marker there was never
  created outside auto mode (DECISIONS.md B3). The line also removes the
  implementing- marker /implement set, which would otherwise keep this issue
  locked, and any authoring- marker /acceptance or /harness left behind
  (DECISIONS.md B8). It is a preprocessing line, so no hook sees it;
  acceptance-guard.sh blocks any tool call that tries to create a verifying- or
  authoring- marker.
-->

# Context

- Unlock: !`mkdir -p .dev-flow-run && rm -f .dev-flow-run/implementing-$ARGUMENTS .dev-flow-run/authoring-$ARGUMENTS && touch .dev-flow-run/verifying-$ARGUMENTS && echo "acceptance reading unlocked for issue $ARGUMENTS"`
- Acceptance: !`cat specs/$ARGUMENTS-*/acceptance.md 2>/dev/null || echo "NO ACCEPTANCE FILE for issue $ARGUMENTS"`
- Acceptance validator: !`python3 .claude/skills/dev-flow/scripts/validate_acceptance.py specs/$ARGUMENTS-*/acceptance.md 2>&1 | head -20`
- Coverage: !`python3 .claude/skills/dev-flow/scripts/coverage.py specs/$ARGUMENTS-* 2>&1 | head -20`
- Attempt: !`bash .claude/skills/dev-flow/scripts/retry_guard.sh $ARGUMENTS status`

# Task

Verify the implementation for issue #$ARGUMENTS against the frozen acceptance cases above.

**Check the freeze first.** If the validator reports `freeze.stale`, the PRD changed
after these cases were written. Stop and tell me — I decide whether the cases or the
requirement moved. Do not update the cases to match the code; that inverts the whole
point of the stage.

For each case: run it if `Type: automated`, and give me the exact steps if
`Type: manual`. Record the outcome per `AC-` id.

**Run the checks through the evidence ledger, never directly.** The project's
own test suite, then the acceptance command, traced to the cases:

```
python3 .claude/skills/dev-flow/scripts/evidence.py run test
python3 .claude/skills/dev-flow/scripts/evidence.py run acceptance 2>&1 | python3 .claude/skills/dev-flow/scripts/ac_trace.py specs/$ARGUMENTS-*/acceptance.md
```

`evidence.py` runs the command from `flow.json`, passes its output through, exits
with the command's exit code, and records that exit code against the exact tree
it ran on. `/review` accepts nothing else: a result you did not produce this way,
or produced before your last edit, counts for nothing there. If it says a command
is not configured, nothing ran; say so, and do not stand in for it by hand.

**Route every failure by cause, not by convenience.** For each failing case, decide:

- **The case is wrong** — it tests something the PRD does not actually require, or
  reads the requirement in a way the PRD does not support. Route back to the PRD.
  Report it to me; do not edit the case.
- **The code is wrong** — the requirement is clear, the case is faithful, the
  implementation misses it. Fix the code and re-verify. Capped at 2 attempts, and
  the counter above is the count. Once it is spent, stop and hand back to me with
  what you tried; a third autonomous attempt on the same failure has never been the
  thing that fixed it.
- **The requirement is wrong** — the case passes or fails as written, but the
  outcome shows the requirement itself was mistaken. Always mine. Stop and say so.

**Exit codes decide when to stop, never your reading of the output.**

- The cases pass only when, on the tree as it now stands, `ac_trace.py` above
  exits 0 and
  `python3 .claude/skills/dev-flow/scripts/evidence.py check test acceptance`
  exits 0. Output that looks green, a test run by hand, or a run from before your
  last edit is not a pass.
- Before each fix attempt, run
  `bash .claude/skills/dev-flow/scripts/retry_guard.sh $ARGUMENTS status`. If it
  exits 1, the cap is spent: make no change, stop, and hand back to me.
  Otherwise run
  `bash .claude/skills/dev-flow/scripts/retry_guard.sh $ARGUMENTS bump` and make
  the attempt. (On the second attempt `bump` prints `EXHAUSTED` and exits 1: that
  attempt still runs, and it is the last.)
- After each fix, run both commands above again through `evidence.py`. Your edit
  made the earlier records STALE.

When you finish, run
`bash .claude/skills/dev-flow/scripts/retry_guard.sh $ARGUMENTS reset`,
then, as a command of its own, `rm -f .dev-flow-run/verifying-$ARGUMENTS`. That
locks the cases again and ends the implementation phase for this issue.

While this session runs, `flow.json`, the lint and format configs and the
acceptance cases cannot be edited (`integrity-guard.sh`, `acceptance-guard.sh`): a
failing case is fixed in the code, or reported, never by weakening a check.

**Report:** pass/fail per `AC-` id, the coverage table, every failure with its
routing decision, and anything under `Not covered` that I should be aware of
before this ships.
