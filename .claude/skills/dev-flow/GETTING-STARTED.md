# Getting started — new project

Fifteen minutes, mostly waiting on installs. Do steps 1–6 once per repo; step 7
onward is the loop you run forever after.

## 0. Prerequisites

```bash
python3 --version     # 3.9+
gh auth status        # GitHub CLI, authenticated
claude --version      # Claude Code
node --version        # 22.20+, only needed for step 5 (skills@1.7.0 declares it)
```

`jq` is optional. The `spec-validate.sh` hook falls back to `sed` without it,
though `jq` is more reliable and worth having; the two guard hooks never use it.

**Windows (Git Bash): `python3` must be real Python.** The validators, the
`spec-validate.sh` hook, `bootstrap.sh` and most commands' context lines call
`python3`. A python.org or Chocolatey install provides only `python.exe`, so the
name `python3` falls through to the Microsoft Store alias, which prints "Python was
not found" instead of running. `python3 --version` above then fails or opens the
Store. Two fixes, either one:

- Put a wrapper on a user PATH directory that comes before `WindowsApps` (for
  example `~/.local/bin/python3`, made executable):

  ```sh
  #!/bin/sh
  exec /c/Python312/python.exe "$@"
  ```

- Or turn off the `python3.exe` alias (Settings → Apps → Advanced app settings → App
  execution aliases) and put a `python3.exe` next to your `python.exe`.

`bootstrap.sh` checks for this and stops before writing anything if `python3` does
not run.

## 1. Put the pipeline somewhere permanent

```bash
git clone <your-fork-or-copy> ~/dev/dev-flow
```

Keep one canonical copy. `bootstrap.sh` copies from it into each repo, so repos
diverge on purpose once installed — updating this copy does not silently change
a project that has already shipped specs against the old rules.

## 2. Create the repo

```bash
mkdir my-project && cd my-project
git init && git commit --allow-empty -m "init"
gh repo create my-project --private --source=. --push
```

The repo must exist on GitHub before `/spec` works — it reads issues with `gh`.

## 3. Install the pipeline

```bash
~/dev/dev-flow/scripts/bootstrap.sh . greenfield
```

The argument after the path is the domain: `greenfield` for anything with no users
yet, `voice-agent` for speech work, `general` otherwise.

An optional third argument (`vercel` or `docker-vps`) also attaches the delivery
layer. Leave it off unless you have read `optional-delivery/README.md` — what it
installs assumes things about your infrastructure.

To see what it would do first, add `--dry-run` before the path: it prints every
file it would write and every change it would merge into `.claude/settings.json`,
and writes nothing.

Read what it printed. Files say `wrote`. The settings lines say what was merged into
`.claude/settings.json`: the three hooks (the acceptance guard, the integrity guard
and the spec validator), the deny rules for secrets, the subagent depth and
`autoMemoryEnabled: false`. If the repo already had that file, it is merged entry
by entry, never replaced, and the original is kept beside it as
`settings.json.bak-<time>`. Check the merge, then delete the backup rather than
commit it. A settings file that is not valid JSON stops bootstrap before it writes
anything: fix the file and run it again. `ACTION` lines need you.

A `WARNING … kept` line means the project already had an entry for one of
dev-flow's hooks that differs from the shipped one, typically because an earlier
dev-flow wired it with an older matcher or timeout. It is kept as it is. To take
the shipped matcher and timeout, run bootstrap again with `--update-hooks` (it
prints each change, backs the file up first, and works with `--dry-run`). It changes
settings entries only, never a hook script or command bootstrap copied earlier;
the README's known limits say how to take those too.
Bootstrap says whether `flow.json` names where the tests `/harness` generates go
(`acceptance_tests`, step 3b), with a `NOTE` when it does not: until it does, nothing
hides them from `/implement`.
Bootstrap also adds `.dev-flow-run/` to `.gitignore`: `/acceptance`, `/harness`,
`/implement` and `/verify` keep the markers the guard hooks read there. And it adds
`__pycache__/`: the validators' bytecode lands beside them, and a file git does not
ignore would make every evidence record STALE (step 9).

## 3b. Fill in flow.json

This is the file that makes the flow language-agnostic, and the one thing bootstrap
cannot do for you. Open `flow.json` and replace the placeholders with your project's
actual commands:

```bash
python3 .claude/skills/dev-flow/scripts/pipeline_config.py
```

It prints what is configured and what will skip. Nothing here is mandatory — a
project with no `lint` command just has no lint step. But two matter more than the
rest:

- `acceptance` — the test command filtered to AC-tagged tests. Without it, nothing
  connects your tests back to your requirements.
- `test` — your full suite, run by `/review` before it readies or merges a PR.

If your acceptance runner can write a JUnit XML report (pytest's `--junitxml`,
Playwright's `junit` reporter, `jest-junit`, `go-junit-report`, most others), have
the `acceptance` command write one and name it in `flow.json`:

```json
"acceptance_junit": "test-results/acceptance-junit.xml"
```

The path is from the project root. `ac_trace.py` then takes each case's pass or
fail from the report instead of scraping the runner's text, which is the safer read
when `autonomy` is `autonomous`. It refuses a report that is missing, malformed or
older than the run it is tracing, rather than falling back to the text. Without the
key it reads the text, and a word counts as a verdict only where a runner prints one.

### Hide the tests `/harness` writes

`/harness` turns the acceptance cases into tests, and those tests spell the cases
out. Name where they go, as a glob from the project root, and dev-flow hides them
from `/implement` as it hides `acceptance.md` (build decision B15):

```json
"acceptance_tests": "**/*.acceptance.test.*"
```

- `/harness` writes its tests only at paths that match it.
- The acceptance guard blocks a Read, Grep, Glob, a Bash, PowerShell or Monitor
  command, or a Skill call's arguments, that names a file matching it: always while
  any issue is being implemented, and otherwise unless `/acceptance`, `/harness` or
  `/verify` has unlocked the cases. The integrity guard blocks writing one while an
  issue is being implemented or verified.
- **Your `test` command must leave them out.** `/implement` runs `test`, and would
  otherwise run them and see their names and failures. A guard sees only what a
  call names, so a command that runs them without naming them is not blocked;
  leaving them out of `test` is what covers that. `/verify` still runs `test` and
  `acceptance` separately, so nothing goes unchecked.

Left empty, as `flow.example.json` ships it, nothing is hidden, and bootstrap and
`pipeline_config.py` say so. The glob is `/`-separated, with `*`, `?` and `**` (a
whole path component) as wildcards and letters, digits and `. _ - @ + ~ % #`
otherwise; `pipeline_config.py --check` rejects anything else, since the guards
read it with bash alone. A glob with no `/` in it matches at any depth.

Per runner, `test` leaves the generated tests out and `acceptance` runs them:

- **vitest**, with the tests beside the code as `*.acceptance.test.ts`. `--exclude`
  adds to vitest's own excludes; `-t AC-` runs the tests whose names carry a case id.

  ```json
  "test": "npx vitest run --exclude '**/*.acceptance.test.*'",
  "acceptance": "npx vitest run -t AC-",
  "acceptance_tests": "**/*.acceptance.test.*"
  ```

- **jest**, the same layout. Leave them out in `jest.config.js`, so `test` names
  nothing: `testPathIgnorePatterns: ['/node_modules/', '\\.acceptance\\.test\\.']`.
  A command-line `--testPathIgnorePatterns` replaces the configured one, which is
  how `acceptance` brings them back.

  ```json
  "test": "npx jest",
  "acceptance": "npx jest --testPathIgnorePatterns=/node_modules/ -t AC-",
  "acceptance_tests": "**/*.acceptance.test.*"
  ```

- **pytest**, with the tests in a directory of their own.

  ```json
  "test": "python -m pytest --ignore=tests/acceptance",
  "acceptance": "python -m pytest tests/acceptance -v",
  "acceptance_tests": "tests/acceptance/**"
  ```

- **Playwright Test**, with `testDir: './tests/acceptance'` as in the config below.
  If Playwright is also your `test` runner, `--grep-invert @AC-` leaves the case
  tests out by title. If `test` is vitest, which would pick up Playwright's
  `*.spec.ts` files too, exclude the directory there instead
  (`npx vitest run --exclude 'tests/acceptance/**'`).

  ```json
  "test": "npx playwright test --grep-invert @AC-",
  "acceptance": "npx playwright test --grep @AC-",
  "acceptance_tests": "tests/acceptance/**"
  ```

`tests/test_guards.py` in the harness repo runs each `test` command above through
both guards while an issue is being implemented, so none of them is blocked.

### If the project has a browser surface: Playwright Test

For acceptance cases a user would check in a browser, make Playwright Test the
`acceptance` command. It is your project's own dev dependency, installed like any
other test runner; dev-flow installs nothing here, and there is no Playwright MCP
(`DECISIONS.md` Q6: the agent never drives a browser, a script runs the tests and
the exit code decides).

```bash
npm i -D @playwright/test
npx playwright install chromium
```

In `flow.json` (JSON has no comments, so `flow.example.json` leaves this empty):

```json
"acceptance": "npx playwright test --grep @AC-"
```

`--grep @AC-` runs only the tests whose title carries an acceptance case id, so
each Playwright test title starts with its id **with the `@`**. A title such as
`AC-003 …` without it is not selected, and its case traces as MISSING:

```ts
import { test, expect } from '@playwright/test';

test('@AC-003 a first-time user completes sign-up unaided', async ({ page }) => {
  await page.goto('/signup');
  // Given / When / Then from the case, with its actual number
});
```

`ac_trace.py` finds `AC-003` in that title, so the trace works as for any runner.
The config below also has Playwright write a JUnit report. Name it in `flow.json`
and the trace reads each test's outcome from it rather than from the `list` lines:

```json
"acceptance_junit": "test-results/acceptance-junit.xml"
```

A `playwright.config.ts` that keeps the test browser away from your own:

```ts
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/acceptance',
  // `list` prints one line per test with its title, which ac_trace.py reads.
  // Set it: Playwright's default under CI is `dot`, which prints no titles.
  // `junit` writes the report flow.json's `acceptance_junit` names; the path is
  // from this file's directory, and `test-results/` is already in .gitignore.
  // The HTML report is kept for you, and never opened: after a failed run in a
  // terminal it would otherwise serve the report and wait for Ctrl+C.
  reporter: [
    ['list'],
    ['junit', { outputFile: 'test-results/acceptance-junit.xml' }],
    ['html', { open: 'never' }],
  ],
  use: {
    baseURL: 'http://localhost:3000',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'], headless: true },
    },
  ],
});
```

- **`chromium`, headless.** Playwright's own browser build, not the Chrome you
  browse with: leave `channel` unset.
- **No profile, no saved sessions.** Each test gets a fresh browser context with
  nothing on disk, which is Playwright Test's default. Keep it that way: no
  `storageState` from outside the repo, no `userDataDir` or persistent context,
  no `connectOverCDP` to a running browser. A test that needs a logged-in user
  logs in as a test account inside the test.
- **Output stays out of git.** `bootstrap.sh` adds `playwright-report/` and
  `test-results/` to `.gitignore` when they are not already there.
- If the tests should start the app themselves, add Playwright's `webServer`
  option with your dev-server command.

Set `autonomy` to `manual` to start: `/review` readies the PR and you merge. Move
it to `autonomous`, where the agent merges, once you trust the checks; it is one
line to change and there is no prize for starting brave. There is no third tier.

## 4. Commit the scaffold

```bash
git add .claude .github specs docs
git commit -m "chore: install spec pipeline"
```

Commit before generating anything. When the first PRD lands you want the diff to
show the PRD, not the PRD plus 30 scaffold files.

## 5. Finish setup inside Claude Code

```bash
claude
```

```
/spec-setup greenfield
```

This installs ten of the Matt Pocock skills as editable files you own, not the
auto-updating plugin. The installer is pinned (`skills@1.7.0`) and so is the skill
pack (one commit of `mattpocock/skills`). It skips the three that compete with this
pipeline, then checks the install: no skill declares `allowed-tools` or `hooks:`,
`.claude/settings.json` and `.mcp.json` are untouched, and `skills-lock.json` pins
every skill to that commit. It also lists back any placeholder thresholds in your
domain pack. It will not fill those in — that is your job and it is the honest
boundary of the whole system.

Commit `.claude/skills/` and `skills-lock.json` afterwards. **Never run
`npx skills update`**: it deletes each skill folder and copies it again, silently
discarding any edit you made. The pin moves only when you change the commit in
`/spec-setup` and re-run it; `/spec-setup` says how.

## 6. Restart, then prove the hooks fire

Exit Claude Code and start it again. `.claude/settings.json` is read at session
start, so the hooks are not live until you do.

Then smoke-test them, because a hook that silently does not fire is worse than no
hook:

```bash
mkdir -p specs/0-smoke
cp .claude/skills/dev-flow/assets/example-prd.md specs/0-smoke/prd.md
```

In Claude Code, ask: *"in specs/0-smoke/prd.md change the Target line to say
'Target: better'"*. The validator hook should fire and push back about the target
having no number. If nothing happens, the hook is not wired — check that
`.claude/settings.json` contains `spec-validate` and that `.claude/hooks/*.sh`
are executable.

Then check the other guard:

```
read specs/0-smoke/acceptance.md
```

There is no acceptance file there, so create one first if you want a true test —
or just trust it and verify at step 9. Clean up either way:

```bash
rm -rf specs/0-smoke
```

## 7. First real loop

```
/grill-me
```

Talk through the idea until it stops producing new questions. Then open an issue
using the **Spec request** template and fill all five fields — problem, who, how
you would know, non-goals, constraints. Thin issues get refused by design, and on
a first run that reads like a broken tool rather than a working gate. The template
applies no label; `spec:auto` is yours to add once step 11 is set up.

If the grilling hits a question that talking cannot settle — does this approach
even work, which of these two shapes is right — stop and build a probe instead:

```
/prototype
```

It works on a `proto/*` branch and is meant to be deleted. When it answers the
question, `/verdict 1` folds the result into the spec as evidence and tells you
how to retire the branch. You can run this before there is a PRD at all; the
verdict comes back shaped for the issue.

```
/spec 1
```

Read the PRD. Expect exit code 2 with several `[NEEDS INPUT]` markers. That is
correct, especially on a greenfield project. Fill in the ones you can answer;
leave the rest.

## 8. Plan, and actually read it

```
/plan 1
```

Read all of it. This is the one mandatory human gate — everything after it spends
compute. When you are satisfied, edit `specs/1-*/plan.md` and set
`status: approved` by hand. Deliberately manual: an agent flipping its own gate
is not a gate.

## 9. Acceptance, then build

```
/acceptance 1
/implement 1
```

`/implement` refuses if the plan is not approved, and then leaves nothing behind
that would block `/acceptance`. It cannot read `acceptance.md`
— if you see it get blocked, the guard is working. Until `/verify` runs it also
cannot edit `flow.json`, the lint and format configs or `acceptance.md`, or skip
git hooks with `--no-verify`.

```
/harness 1
/implement 1
/verify 1
```

`/harness` turns the acceptance cases into real tests, in a forked context that
never sees your implementation, and writes them where `acceptance_tests` says
(step 3b). `/implement` refuses if the plan is not approved and cannot read
`acceptance.md`, or those tests while the glob is set. `/verify` routes failures by cause: wrong case
goes back to the PRD, wrong code gets at most two automatic attempts, wrong
requirement always comes to you. It runs your `test` and `acceptance` commands
through `scripts/evidence.py`, which records each exit code against the exact
tree it ran on, in `.dev-flow-run/evidence.jsonl`. Commit what `/verify` tested:
`/review` accepts that evidence only for the tree the branch commits.

## 10. Review and merge

```
/review 1
```

Runs your configured lint command, and checks that `/verify`'s test and acceptance
evidence is FRESH for the committed tree: an edit after `/verify` makes it STALE,
and the PR then stays a draft until you run `/verify 1` again. It also checks
that commits cite requirement ids, and flags any file the plan did not mention. With the Pocock `code-review`
skill installed, it hands the craft review to that skill, with the PRD as its spec.
Then it opens or updates the PR, with `Closes #1` in its body, and, when everything
is clean, marks it ready for review; you merge. At `autonomous` it also merges. A
project with no `lint` command gets "lint: not configured" in the PR body, and the
PR is readied all the same; `test` and `acceptance` must have run through `/verify`.

That is where this flow ends. Release, deployment, and measuring whether the work
achieved its goal are project-specific — see `optional-delivery/README.md` if you
want them, and expect to edit what it gives you.

## 11. Optional — headless

Add `CLAUDE_CODE_OAUTH_TOKEN` to repo secrets — the runs authenticate with your
Claude subscription, not a pay-per-use API key. Generate the token with
`claude setup-token`. Then label any issue `spec:auto` and the PRD arrives as a
PR without you typing anything. Untested against a live repo — treat the first
run as an experiment, on an issue you do not mind mangling.

You also have to turn on **Settings → Actions → General → "Allow GitHub Actions
to create and approve pull requests"**. Without it the job does all the work,
pushes the branch, and then fails on the last step with *"GitHub Actions is not
permitted to create or approve pull requests"* — the PRD is on the branch, but
no PR opens. Observed on a live run.

The job only starts for issues opened by someone with write access, labelled or
dispatched by someone with write access. Anything else gets a comment on the
issue and nothing else, because the step after this one hands issue text to a
model that can write to the repository. That text arrives wrapped by
`scripts/issue_envelope.py` and the model step holds no `GH_TOKEN`.

---

## If something misbehaves

| Symptom | Cause |
|---|---|
| `/spec` says no issue found | `gh auth status`, and check the repo has a remote |
| Hooks never fire | Restart the session; check `.claude/settings.json` and `chmod +x .claude/hooks/*.sh` |
| "Python was not found" in command output (Windows) | `python3` is the Microsoft Store alias — see step 0 |
| Validator flags legitimate `<generics>` | Loosen `TEMPLATE_PLACEHOLDER_RE` in `validate_prd.py` |
| `/spec` refuses a reasonable issue | Fix the issue template, not the skill — the gate is doing its job |
| `/grill-me` asks no numbered round, or says `grilling` is missing | An install from before the pin, which left out `grilling`. Run `/spec-setup` again |
| Everything exits 2 forever | Correct. Fill in the numbers or accept the markers; nothing gates on 2 |
| Acceptance cases show MISSING | No test carries that AC id. Run `/harness`, or move the case to Not covered |
| Playwright says "No tests found", every case MISSING | The titles lack the `@`: `--grep @AC-` needs `@AC-001 …` (step 3b) |

| Steps say "skipped" | That command is not in `flow.json`. Add it, or accept the gap knowingly |
| A marker nobody can answer | Nobody knows it yet — that is a `/prototype`, not a question for a human |
| Prototype PR blocked by CI | Working as designed. Run `/verdict`, then delete the branch |
