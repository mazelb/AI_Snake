---
description: One-time setup of the spec pipeline in this repo
argument-hint: [voice-agent|greenfield|general]
allowed-tools: Bash, Read, Write, Edit, Glob
disable-model-invocation: true
---

# Current state

- Skill installed: !`test -d .claude/skills/dev-flow && echo yes || echo NO`
- Commands: !`ls -1 .claude/commands/ 2>/dev/null || echo "(none)"`
- Default domain: !`cat .claude/skills/dev-flow/DEFAULT_DOMAIN 2>/dev/null || echo "(unset)"`
- Hook wired: !`grep -q spec-validate .claude/settings.json 2>/dev/null && grep -q acceptance-guard .claude/settings.json 2>/dev/null && grep -q integrity-guard .claude/settings.json 2>/dev/null && echo yes || echo NO`
- Matt Pocock skills: !`ls -1 .claude/skills/ 2>/dev/null | grep -xE 'grill-me|grill-with-docs|grilling|domain-modeling|prototype|tdd|codebase-design|diagnosing-bugs|code-review|writing-for-agents' || echo "(not installed)"`

# Task

Finish setting up the spec pipeline here. Domain: $ARGUMENTS (default `general` if empty).

1. Repair what the lines above say is missing. Never run the installed copy of
   `bootstrap.sh` (`.claude/skills/dev-flow/scripts/bootstrap.sh`): the installed
   skill carries its scripts, references and assets, but not the commands or the
   hook scripts, so a bootstrap run from there stops halfway, at the commands.
   - **"Hook wired" says NO:** the settings can be repaired from the installed copy.
     From the repository root, run this as one Bash command, exactly as written,
     and show me its whole output:
     `python3 .claude/skills/dev-flow/scripts/settings_merge.py .claude/skills/dev-flow/assets/settings.hook.json .claude/settings.json; echo "merge exit code: $?"; ls .claude/hooks/spec-validate.sh .claude/hooks/acceptance-guard.sh .claude/hooks/integrity-guard.sh`
     The merge is the one bootstrap runs. "Hook wired" needs the `spec-validate`,
     the `acceptance-guard` and the `integrity-guard` hook in
     `.claude/settings.json`; the merge adds whichever is missing, backs the file
     up first, keeps every other setting, and stops without writing anything if
     the file does not parse. If it stopped, show me why and go on to step 2.
     Otherwise run the "Hook wired" line above again, as it stands, and tell me
     what it says; if it still says NO, tell me which of the three is missing and
     show me the merge's output. The `ls` checks that the three scripts the
     entries run exist: name any it cannot find, and treat it as the next case.
   - **"Skill installed" says NO, "Commands" says "(none)", or a hook script is
     missing:** nothing in this repository can repair that. Tell me what is
     missing and to run bootstrap from
     my dev-flow checkout, `<checkout>/dev-flow/scripts/bootstrap.sh . $ARGUMENTS`,
     which adds only the files that are missing, then to run `/spec-setup` again.
     Do not copy or write those files yourself. Go on to step 2.
2. If any of the ten Matt Pocock skills named in the block below is missing from the
   list above, install them. Run the block **as one Bash command, exactly as
   written**, from the repository root, and show me its whole output. It installs
   pinned, editable copies (not the auto-updating plugin) and then checks what it
   installed.

   ```bash
   snap() { for f in .claude/settings.json .claude/settings.local.json .mcp.json; do printf '%s ' "$f"; cksum < "$f" 2>/dev/null || echo absent; done; }
   before="$(snap)"

   DO_NOT_TRACK=1 npx -y skills@1.7.0 add \
     'https://github.com/mattpocock/skills#c55ee46073ed923f86ce59a5eb3b6d895095d1b7' \
     --agent claude-code --copy -y \
     --skill grill-me grill-with-docs grilling domain-modeling prototype tdd codebase-design \
             diagnosing-bugs code-review writing-for-agents
   echo "install exit code: $?"

   # Post-install check
   fail=0
   for s in grill-me grill-with-docs grilling domain-modeling prototype tdd codebase-design diagnosing-bugs code-review writing-for-agents; do
     if [ -f ".claude/skills/$s/SKILL.md" ] && [ ! -L ".claude/skills/$s" ]; then :; else echo "FAIL: .claude/skills/$s is missing or is a link"; fail=1; fi
     if grep -nE '^(allowed-tools|hooks):' ".claude/skills/$s/SKILL.md" 2>/dev/null; then echo "FAIL: $s declares allowed-tools or hooks"; fail=1; fi
   done
   for s in to-spec to-tickets implement; do
     if [ -e ".claude/skills/$s" ]; then echo "FAIL: .claude/skills/$s is installed, and it competes with dev-flow"; fail=1; fi
   done
   if [ -e .agents ]; then echo "FAIL: .agents/ exists, so the install did not use --copy"; fail=1; fi
   if [ "$before" != "$(snap)" ]; then echo "FAIL: .claude/settings.json, .claude/settings.local.json or .mcp.json changed"; fail=1; fi
   if ! python3 -c 'import json, sys; lock = json.load(open("skills-lock.json", encoding="utf-8"))["skills"]; sys.exit(any(lock.get(n, {}).get("source") != "mattpocock/skills" or lock.get(n, {}).get("ref") != sys.argv[1] for n in sys.argv[2:]))' c55ee46073ed923f86ce59a5eb3b6d895095d1b7 grill-me grill-with-docs grilling domain-modeling prototype tdd codebase-design diagnosing-bugs code-review writing-for-agents 2>/dev/null; then echo "FAIL: skills-lock.json is missing, or does not pin every skill to mattpocock/skills#c55ee46073ed923f86ce59a5eb3b6d895095d1b7"; fail=1; fi
   if [ "$fail" = 0 ]; then echo "post-install check: PASS"; else echo "post-install check: FAIL"; false; fi
   ```

   - `skills@1.7.0` pins the installer, and `#c55ee46…` pins the skill pack to one
     commit. `skills-lock.json` records that commit; commit it with the skills.
   - `grilling`, `domain-modeling` and `codebase-design` are required: `grill-me`,
     `grill-with-docs` and `tdd` only call them.
   - `to-spec`, `to-tickets` and `implement` are deliberately left out. The dev-flow
     skill is our spec spine, and two competing PRD generators in one repo is worse
     than either alone.
   - `--copy` writes real directories rather than links, so the copies are files
     this repo owns and they work on every machine. `DO_NOT_TRACK=1` turns off the
     installer's telemetry.

   If the output ends in `post-install check: FAIL`, stop and show me. Do not edit
   the skills, the settings or `skills-lock.json` to make it pass.

   **Never run `npx skills update`, and never `skills@latest`.** `update` deletes
   each skill folder and copies it again, with no check for local edits, so it
   silently destroys any change made to the copies. The pin moves only on purpose:
   change the commit in this block, read the upstream diff
   (`git log <old>..<new> -- skills/` in a clone of `mattpocock/skills`), run the
   block again, and review `git diff` here.
3. Read `.claude/skills/dev-flow/references/$ARGUMENTS.md` and list back the
   placeholder thresholds I need to replace with real measured numbers. Do not
   fill them in yourself.
4. Show me the resulting tree and stop. Do not write a PRD. Remind me that after I
   restart Claude Code, `/hooks` should list dev-flow's three hooks and nothing new
   besides my own, `/mcp` should show no new server, and `/grill-me` should open
   with a numbered round of questions: that round is the `grilling` skill, which
   `grill-me` only calls.
