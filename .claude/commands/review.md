---
description: Pre-merge review of a change against its plan, PRD and coverage
argument-hint: <issue-number>
allowed-tools: Bash, Read, Grep, Glob
disable-model-invocation: true
---

# Context

- Branch: !`git branch --show-current`
- Diff stat: !`git diff --stat $(git merge-base HEAD origin/HEAD 2>/dev/null || echo HEAD~1)...HEAD 2>&1 | tail -20`
- Commits: !`git log --oneline $(git merge-base HEAD origin/HEAD 2>/dev/null || echo HEAD~1)...HEAD 2>&1 | head -20`
- Plan: !`cat specs/$ARGUMENTS-*/plan.md 2>/dev/null | head -60 || echo "(no plan)"`
- Coverage: !`python3 .claude/skills/dev-flow/scripts/coverage.py specs/$ARGUMENTS-* 2>&1`
- Autonomy: !`python3 .claude/skills/dev-flow/scripts/pipeline_config.py --autonomy 2>&1`
- Lint: !`python3 .claude/skills/dev-flow/scripts/evidence.py run lint 2>&1 | tail -15`
- Evidence: !`python3 .claude/skills/dev-flow/scripts/evidence.py check --against HEAD test acceptance 2>&1 | tail -20`
- Fixed point: !`git merge-base HEAD origin/HEAD 2>/dev/null || echo HEAD~1`
- PRD: !`ls specs/$ARGUMENTS-*/prd.md 2>/dev/null || echo "(no PRD)"`
- Craft reviewer: !`test -f .claude/skills/code-review/SKILL.md && echo "code-review installed" || echo "(code-review not installed)"`

# Task

Review this change before it merges. Three layers, in order:

**1. Mechanical.** Report the lint result and the evidence above as-is, grade by
grade. The grades come from `evidence.py`, not from you. `test` and `acceptance`
are clean only when `FRESH` with exit 0: they ran through `/verify` on exactly
the tree this branch commits. `STALE` means they ran on a different tree (an edit
since, uncommitted changes, or a changed command) and prove nothing about this
one; `MISSING` means they never ran through the ledger. Neither is clean, and you
do not re-run them yourself to make them green: tell me to run
`/verify $ARGUMENTS` on the committed tree. If lint says it is not configured,
report `lint: not configured`, here and in the PR body. That is not a pass, and
it does not hold the PR back either: `flow.json` has no lint command, and an
unconfigured step skips loudly. A configured lint must pass. `test` and
`acceptance` have no such exemption: one that is not configured never ran
through the ledger, so it is MISSING and not clean. When the coverage above says
the plan skips acceptance, no `acceptance` evidence is expected: say it is
skipped by the plan, with the plan's reason, and hold `test` to the same rule (if it is not `FRESH`,
the command that records it is
`python3 .claude/skills/dev-flow/scripts/evidence.py run test`).

**2. Traceability.** Does every commit cite a task and requirement? Does the diff
touch files the plan did not mention, and if so, why? Does the coverage table show
anything unimplemented or untested? A change that quietly exceeds its plan is the
thing this layer exists to catch.

**3. Craft.** If the craft reviewer above says `code-review installed`, delegate to
that skill (Pocock's `code-review`, which `/spec-setup` installs into
`.claude/skills/`): run it with the Skill tool, and pass it the fixed point and the
PRD path above as its arguments, saying that the PRD is the spec, that no issue is
to be fetched, and that it must not search `docs/`, `specs/` or `.scratch/` for
another spec. Passing the path is what stops that search, which would otherwise
find `specs/*/acceptance.md`. If the PRD line says there is none, tell it there is
no spec, so its Spec axis reports "no spec available" rather than looking for one.

If the craft reviewer says `code-review` is not installed, do not invoke any skill
of that name: Claude Code bundles its own `code-review`, which takes a path as the
thing to review rather than as the spec. Review the craft yourself instead:
correctness, error handling, obvious performance traps, and whether the code will
be legible to you in six months.

**Do not read `specs/*/acceptance.md`.** A hook blocks it, and the reason still
holds during review: if the review is informed by the acceptance cases, the review
stops being independent of them.

Then act on the autonomy tier above. There are two tiers, and only `autonomous`
merges:

- `manual` — report, then open the PR for this branch, or update it if one exists:
  push the branch, then `gh pr create --draft`, or `gh pr edit`. The body's first
  line is `Closes #$ARGUMENTS`, so merging the PR closes the issue, and the rest
  summarises the three layers, naming any step that is not configured.
  If all three layers are clean, mark it ready for review (`gh pr ready`).
  Do not merge it. I merge.
- `autonomous` — the same, and then, if all three layers are clean, merge it
  (`gh pr merge --merge`, which keeps each commit and the ids it cites).
- Anything else, or an error, is not a tier (`assisted` was removed). Report, open
  nothing, merge nothing, and tell me to fix `flow.json`
  (`python3 .claude/skills/dev-flow/scripts/pipeline_config.py --check`).

If the branch above is the repository's default branch, there is no PR to open:
report and stop. If anything is not clean, leave the PR a draft, stop and report.
An unconfigured lint, reported as above, is not a reason to.
Never mark it ready or merge it past a failing check because the failure looks
unrelated; say it looks unrelated and let me decide.

Readying the PR at `manual`, or merging it at `autonomous`, is where your
responsibility ends. What happens after — release, deployment, measuring whether
it worked — is project-specific and not part of this flow. If the project has a
delivery layer attached, say so and stop; do not invoke it.
