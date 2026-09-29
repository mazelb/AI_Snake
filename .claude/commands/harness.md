---
description: Generate executable tests from the frozen acceptance cases
argument-hint: <issue-number>
allowed-tools: Bash(python3 .claude/skills/dev-flow/scripts/pipeline_config.py --get *), Bash(python3 .claude/skills/dev-flow/scripts/ac_trace.py *), Bash(mkdir -p .dev-flow-run), Bash(touch .dev-flow-run/authoring-*), Bash(rm -f .dev-flow-run/authoring-*), Read, Write, Edit, Grep, Glob
context: fork
disable-model-invocation: true
---

<!--
  No bare `Bash` grant (DECISIONS.md DR1). The grants left are the scripts the
  context lines and the task below run; the `cat` and `ls` lines are read-only
  commands and need none. The acceptance command itself is project-specific,
  so it goes through the normal permission rules and may prompt.

  The Stage line sets .dev-flow-run/authoring-<issue> (DECISIONS.md B8): the
  trace below names acceptance.md, and without it acceptance-guard.sh blocks
  it. The model removes it with an rm of its own at the end. The marker grants
  end in `authoring-*`, not ` *`: the argument placeholder is not filled in
  allowed-tools, and `Bash(rm -f *)` would allow any removal (build item 26).
-->

# Context

- Stage: !`mkdir -p .dev-flow-run && touch .dev-flow-run/authoring-$ARGUMENTS && echo "writing tests from the acceptance cases for issue $ARGUMENTS"`
- Acceptance cases: !`cat specs/$ARGUMENTS-*/acceptance.md 2>/dev/null || echo "NO ACCEPTANCE FILE — run /acceptance $ARGUMENTS first"`
- Test command: !`python3 .claude/skills/dev-flow/scripts/pipeline_config.py --get test 2>&1`
- Acceptance command: !`python3 .claude/skills/dev-flow/scripts/pipeline_config.py --get acceptance 2>&1`
- Existing test files: !`ls -R tests test spec __tests__ 2>/dev/null | head -30 || echo "(none found)"`

# Task

Turn the acceptance cases above into tests that actually run.

You are in a forked context and you must **not read the implementation**. These
tests come from the cases, which came from the PRD. Reading the code to find out
what to assert defeats the entire chain — the point is that these tests were
written by something that had never seen the code.

Reading existing *test* files to match conventions is fine and expected: use the
project's runner, its directory layout, its assertion style, its fixture patterns.
Do not invent a new testing idiom.

**Every test name must contain its case id.** This is the only link between the
markdown and the runner, and `ac_trace.py` reads it by text match:

- `test("AC-001 offline state surfaces quickly", ...)`
- `def test_ac_002_state_survives_disconnection():`

`AC-001`, `ac-001`, `ac_001` and `AC001` all trace. A test without its id is
invisible to the flow, and its case reports as MISSING rather than passing.

For each case: `Given` becomes setup, `When` becomes the action, `Then` becomes
the assertion with its actual number, `Fails if` tells you what the test must
catch — use it to check your assertion is not trivially satisfiable.

Skip cases marked `Type: manual`. They run by hand and trace as MANUAL.

If a case cannot be automated with what the project has — no test harness for that
layer, no way to simulate the condition — say so instead of writing a test that
asserts something weaker. Then tell me, so it either moves to manual or the
missing infrastructure becomes its own issue.

Finally, run the acceptance command and trace it:

```
<acceptance command> 2>&1 | python3 .claude/skills/dev-flow/scripts/ac_trace.py specs/$ARGUMENTS-*/acceptance.md
```

Report the trace table. Every MISSING is either a test you still owe or a case
that needs moving — never a pass.

Your last command, after everything else and whatever the outcome, is
`rm -f .dev-flow-run/authoring-$ARGUMENTS`, as a command of its own. It locks the
cases again: after it, nothing in this session can read them, so run nothing
that names them afterwards.
