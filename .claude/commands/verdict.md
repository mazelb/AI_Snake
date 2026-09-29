---
description: Fold a prototype's verdict into the spec as evidence, and delete the prototype
argument-hint: <issue-number>
allowed-tools: Bash(git *), Bash(gh *), Bash(python3 *), Bash(cat *), Bash(ls *), Read, Write, Edit, Grep, Glob
disable-model-invocation: true
---

# Context

- Current branch: !`git branch --show-current`
- Prototype branches: !`git branch --list 'proto/*' | sed 's/^..//' || echo "(none)"`
- Spec: !`ls -1 specs/$ARGUMENTS-*/ 2>/dev/null || echo "(no spec dir for issue $ARGUMENTS yet)"`
- Open questions: !`sed -n '/## Open questions/,$p' specs/$ARGUMENTS-*/prd.md 2>/dev/null || echo "(no PRD yet)"`
- Blocked items: !`python3 .claude/skills/dev-flow/scripts/validate_prd.py specs/$ARGUMENTS-*/prd.md 2>&1 | sed -n '/blocked/,/^$/p' || true`

# Task

A prototype has answered a question. Fold the answer into the spec for issue #$ARGUMENTS
and get rid of the prototype.

**What survives is the decision, not the code.** The prototype was built to be
thrown away — its value is entirely in what it settled. Do not merge it, do not
copy chunks of it into the implementation, and do not treat it as a starting point.

1. **Establish the verdict.** Ask me what the prototype showed if it is not
   already obvious from the conversation. Write it as what was *learned*, with the
   number or the observed behaviour — not "the state model works."

2. **Find what it resolves.** Match the verdict against the open questions and
   `[NEEDS INPUT]` markers above. A prototype usually settles one of three things:
   an unknown number, an ambiguous requirement, or a choice between approaches.

3. **Update the PRD:**
   - Add an entry under `## Evidence` with Question, Verdict, Prototype branch,
     and Date.
   - Resolve the matching `[NEEDS INPUT]` marker or open-question row **only if
     the prototype genuinely measured it.** A prototype that demonstrates a state
     machine holds up does not tell you your production p95 — do not let a nearby
     result close an unrelated gap.
   - If the verdict changed a requirement, edit the requirement and say so in your
     report. If it invalidated one, mark it `[WITHDRAWN]` in place rather than
     deleting it, so downstream references survive.
   - When a measured number becomes the metric source, write
     `Source: prototype:proto/<branch>`.

4. **If there is no PRD yet**, that is fine and often correct — the prototype ran
   before the spec. Output the verdict as a comment I can paste on the issue, in
   the shape the issue template expects, so `/spec $ARGUMENTS` starts from it.

5. **Retire the prototype.** Confirm the branch is pushed and not merged into the
   default branch, then tell me the exact command to delete the local branch. Do
   not delete it yourself — that is mine to run once I have seen the diff.

6. **Re-validate:** `python3 .claude/skills/dev-flow/scripts/validate_prd.py specs/$ARGUMENTS-*/prd.md`

**Report:** what the prototype settled, what it did *not* settle that I might
assume it did, and which blocked items are still open.
