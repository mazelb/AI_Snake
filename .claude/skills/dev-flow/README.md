# dev-flow

Specs and automated development agents for personal projects. Idea to verified,
merge-ready code.

```
/grill-me ─┬─ /prototype ── /verdict ─┐
           └───────────────────────────┴─→ issue
                                            ↓
            /spec ──→ prd.md ──→ /plan ──→ plan.md ──→ [YOU APPROVE]
                                    │
                 /acceptance ───────┤
                       ↓            │
                 acceptance.md ──→ /harness ──→ tests
                 (frozen, hidden)   │
                                    └──→ /implement ──→ code
                                                ↓
                                            /verify ──→ /review ──→ merge
```

Everything after merge — release, deployment, measuring outcomes — is
project-specific and lives in `optional-delivery/`.

Language-agnostic: every command the agents run is read from `flow.json`, so the
same flow drives a TypeScript project and a Python one.

## Install

```bash
./scripts/bootstrap.sh /path/to/repo <domain>
./scripts/bootstrap.sh --dry-run /path/to/repo <domain>   # print every write and merge, do none
./scripts/bootstrap.sh --update-hooks /path/to/repo <domain>   # also take the shipped hook matchers and timeouts
```

Then `/spec-setup <domain>` in Claude Code, restart the session, and fill in
`flow.json`. Full walkthrough in `GETTING-STARTED.md`. If `.claude/settings.json`
later loses one of dev-flow's hook entries, `/spec-setup` puts it back with the
installed copy's settings merge; missing commands or hook scripts need
`bootstrap.sh` from a dev-flow checkout, since the installed copy carries neither.

Bootstrap never overwrites a file. It changes two in place. It merges its settings
into the project's `.claude/settings.json` (`scripts/settings_merge.py`, from the
data in `assets/settings.hook.json`). Each hook entry is matched by its script
name, and one already present is kept as it is, with a warning when its matcher or
timeout differ from the shipped ones. `--update-hooks` gives such an entry the
shipped matcher and timeout, and changes nothing else in it; a project hook that
shares its group keeps its own matcher (DECISIONS.md B4). Missing deny rules are
appended.
`env` and `autoMemoryEnabled` are set to the shipped values, with any old value
reported. Every other key is left alone. An existing file is backed up to
`settings.json.bak-<time>` first. A file that does not parse, or has the wrong
shape, stops the install before anything is written. A re-run with nothing to add
writes nothing. Nothing machine-specific goes into `settings.json`; that belongs in
`settings.local.json`, which bootstrap never writes. It only warns when that file
overrides a merged setting on this machine.

It also appends `playwright-report/` and `test-results/` to the project's
`.gitignore` (created if absent) when they are not already there, for projects
that use Playwright Test as their acceptance command (`GETTING-STARTED.md` step
3b), `.dev-flow-run/`, where `/acceptance`, `/harness`, `/implement` and
`/verify` keep the markers the guard hooks read, and `__pycache__/`, where Python
puts the validators' bytecode, which would otherwise make every evidence record
STALE. Existing lines are never changed, and a re-run adds nothing.

## The two halves

**Specs** — `/spec`, `/spec-review`, `/verdict`. Turns an agreed issue into a PRD
with numbered requirements and checkable acceptance conditions, or refuses if the
issue is too thin to spec without inventing the gaps.

**Development agents** — `/plan`, `/acceptance`, `/harness`, `/implement`,
`/verify`, `/review`. Decompose, design the tests, build, verify, review.

## flow.json

Commands are named, not assumed: `install`, `lint`, `typecheck`, `test`,
`acceptance`, `build`. An unconfigured command is not an error — that step skips
loudly. `/review` reports an unconfigured `lint` as "not configured" and readies
the PR all the same; `test` and `acceptance` have no such pass, since `/review`
needs their evidence from `/verify` (build decision B16).

`autonomy` is per project, and there are two tiers:

| Tier | Means |
|---|---|
| `manual` | `/review` reports, opens or updates the PR, and marks it ready for review when all three layers are clean; you merge |
| `autonomous` | The same, and then the agent merges |

Any other value is rejected by `pipeline_config.py --check` and by `--autonomy`,
and `/review` then opens and merges nothing. There is no third tier: `assisted` was
removed (build C2 in the harness repo's `DECISIONS.md`). Neither tier deploys;
that is `optional-delivery/`.

`python3 scripts/pipeline_config.py --gates` lists what holds at every tier.

`acceptance_tests` is a glob from the project root naming where `/harness` writes
the tests it generates from the acceptance cases (`**/*.acceptance.test.*`,
`tests/acceptance/**`). The guards lock the files it matches as they lock
`acceptance.md` (below; build decision B15), and the `test` command should leave
them out; `GETTING-STARTED.md` step 3b shows how for vitest, jest, pytest and
Playwright Test. `flow.example.json` ships it empty, and empty or unset nothing is
hidden: bootstrap and `pipeline_config.py` say so. `pipeline_config.py --check`
rejects a glob the guards could not read.

## The ID contract

`REQ-001` is permanent and never renumbered. Plan tasks declare
`Satisfies: REQ-001`; acceptance cases are `AC-001 [REQ-001]`; generated tests
carry the case id in their name; commits cite the `TASK-` and the `REQ-`.

Every task also has a `Seams:` line — where its tests attach, or
`Seams: none — <reason>` — and approving the plan confirms them for `/tdd`.

**Work with no PRD.** A plan may skip steps: `## Skipped steps` lists each with a
reason, and approving the plan approves them. Only `prd` and `acceptance` can be
skipped. When the PRD is skipped, tasks cite the issue, `Satisfies: #42`, and
commits cite the `TASK-` and the issue. `validate_plan.py` accepts `#42` only
with the PRD skip recorded. There are no acceptance cases for such work, so no
`/verify` evidence.

`coverage.py` then answers mechanically: what is unimplemented, what is untested,
and what is being built that nobody asked for. A plan that skips the PRD is
reported as "no PRD — issue-cited", not as missing.

`validate_plan.py` warns when a task has no `Touches:`, and fails it when
`flow.json` has `unattended.enabled: true`, since an unattended run holds each
task to its `Touches:`.

## Exit codes

`0` clean · `1` structural errors · `2` blocked on a human.

`2` is a healthy state and nothing gates on it. The moment it does, everyone —
human and agent — learns to invent numbers to get a green tick.

`coverage.py` has its own: `0` covered · `1` gaps · `3` a spec is missing its PRD or
declares no requirements · `4` no specs yet. So does `evidence.py check`: `0` every
check FRESH with exit 0 · `1` a FRESH check failed · `2` STALE or MISSING · `3`
cannot check; `evidence.py run` exits with the command's own code. `deliver.yml`'s gate fails on `1` and
`3` and lets `4` through with a notice.

## Enforced boundaries

**The plan is the human gate.** `/implement` refuses unless `status: approved`, and
only a hand edit sets that. It sets its implementing marker only for an approved
plan, so a refusal leaves nothing that locks the issue.

**Acceptance cases are hidden from the coding agent.** `acceptance-guard.sh` blocks
access to `specs/<n>-<slug>/acceptance.md` by Read, Grep, Glob, and a command run by
Bash, PowerShell (Claude Code's shell tool on Windows) or Monitor, or named in a
Skill call's arguments, unless a stage that reads the cases has unlocked that issue,
and blocks Write, Edit and NotebookEdit of the file while any issue is being
implemented or verified. Every tool Claude Code offers is classed in
`tests/test_guards.py`, and a tool a new release adds fails that test until it is
classed and, if it can read a file or run a command, wired to both guards (build
item 27). `/verify <n>` unlocks by
creating `.dev-flow-run/verifying-<n>` in a preprocessing line, and `/acceptance <n>`
and `/harness <n>` by creating `.dev-flow-run/authoring-<n>`, so they can run their
own checks on the cases; each removes its marker when it finishes. An `authoring-`
marker does not start the implementing phase, so `/acceptance` can still write the
file. `/implement <n>` creates `.dev-flow-run/implementing-<n>`, which keeps issue n
locked whatever else is lying around, and removes any `authoring-<n>`; `/verify`
removes both. A tool call that tries to create a `verifying-` or `authoring-` marker
is blocked. Its gaps are under Known limits. Code written against visible
tests passes those tests without necessarily satisfying the requirement behind them.

**So are the tests generated from them** (build item 30), once `flow.json` sets
`acceptance_tests`. `/harness` writes its tests only where that glob points, and
the acceptance guard treats a file it matches as it treats `acceptance.md`, through
the same tools: a call naming one is blocked while any issue is being implemented,
and otherwise unless an `authoring-` or `verifying-` marker exists (the tests belong
to no one issue's directory, so any such marker unlocks them); so is a Grep over the
glob's own directory or one holding it, and a Write, Edit or NotebookEdit of one
while an issue is being implemented or verified. A word holding `*` or `?` names no
file in a command or a Skill call's arguments, so the `test` command's `--exclude
'**/*.acceptance.test.*'` runs; in a Grep's glob or a Glob's pattern it counts. The
`test` command leaving them out is what keeps the implementer's own test runs from
running them; `/verify` runs `test` and `acceptance` separately.

**The checks are not weakened to get a green run.** `integrity-guard.sh` blocks
`--no-verify`, `git commit -n` and any `core.hooksPath` change at all times, and a
Write or Edit of a `prd.md` or `plan.md` that drops a `REQ-` or `TASK-` id the file
has (ids are permanent; mark one `[WITHDRAWN]` in place). While an issue is being
implemented or verified it also blocks edits to `flow.json`, the lint, format and
git-hook configuration files it lists, and `acceptance.md`, by the Write, Edit and
NotebookEdit tools and by the commands that plainly write a file, run by Bash,
PowerShell (`Set-Content`, `Out-File`, `>` and the rest) or Monitor, and the same
for the generated acceptance tests when `acceptance_tests` is set (there a pattern
counts: `rm src/*.acceptance.test.ts` is blocked). Outside that phase they
are yours to edit, and `/spec-setup` fills in `flow.json`.

**Tests are generated in a forked context.** `/harness` sees the cases and the
project's existing test conventions, never the implementation.

**Fix attempts are capped at 2.** `retry_guard.sh`. A third autonomous attempt on
the same failure has never been the thing that fixed it.

**"It passed" is a record, not a claim.** `/verify` runs `test` and `acceptance`
through `scripts/evidence.py`, which runs the `flow.json` command, passes its
output through, and appends to `.dev-flow-run/evidence.jsonl` the command's
sha256, its exit code, the commit, and the tree fingerprint before and after.
`evidence.py check` grades each: FRESH (same command, same tree, not edited
during the run), STALE, or MISSING. `/review` layer 1 accepts only FRESH with
exit 0, for the tree the branch commits (`--against HEAD`), and never re-runs
the checks itself. `/verify` stops on exit codes and `retry_guard.sh`, not on its
reading of the output. The ledger holds exit codes and tree ids, never output,
so no acceptance case text reaches it.

**Auto memory is off.** Bootstrap writes `"autoMemoryEnabled": false` into the
project's `.claude/settings.json` (DR2 in the harness repo's `DECISIONS.md`).
Claude Code's own auto memory would otherwise save notes to
`~/.claude/projects/<project>/memory/` and load `MEMORY.md` into every later
session, a route the acceptance guard cannot see. The file is in version control,
so the setting holds on every machine and in CI. **The rule behind it (A9): no
hook, plugin or memory feature may persist session content, or re-inject it into
a later session, in a repository that keeps acceptance cases hidden.** That
includes Claude Code's own auto memory, a plugin's memory or session-start hooks,
and anything installed later. What the switch does not cover is under Known limits.

**Secrets are denied to every session (DR1 tier 1).** The same file carries
`permissions.deny` rules, which hold on both machines and in CI, with no timeout:
`Read(**/.env)`, `Read(**/.env.*)`, `Read(**/*.pem)`, `Read(**/*.key)`,
`Read(~/.ssh/**)`, `Read(~/.aws/**)`, `Read(~/.config/gh/**)`,
`Read(~/.git-credentials)`, `Read(~/.netrc)`, `Read(~/.docker/config.json)`,
`Read(~/.npmrc)` and `Edit(.github/workflows/**)`. **So are the session
transcripts** (`Read(~/.claude/projects/**)`, build item 31, DECISIONS.md B18):
Claude Code writes every session there, and the first real run found the cases in the
transcripts of `/acceptance`, `/harness` and `/verify`, where a later `/implement`
could have read them. It also sets
`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1`, so a sub-agent cannot start its own. A
deny rule anywhere beats an allow rule anywhere, including `--allowedTools` and a
command's `allowed-tools`. What the rules do not stop is under Known limits.

## Commands

| Stage | Command |
|---|---|
| Setup | `/spec-setup <domain>` |
| Align | `/grill-me`, `/prototype`, `/verdict 14` |
| Spec | `/spec 14`, `/spec-review 14` |
| Plan | `/plan 14` → you approve |
| Test design | `/acceptance 14`, `/harness 14` |
| Build | `/implement 14`, `/verify 14` |
| Merge | `/review 14` |
| Anytime | `/spec-check`, `/coverage` |

## Artifacts per issue

`specs/<n>-<slug>/` holds `prd.md`, `plan.md`, `acceptance.md`. Each has a
validator; the `spec-validate.sh` hook runs the right one automatically whenever
Claude writes one.

## What runs unattended

`spec-pipeline.yml` — label an issue `spec:auto`, get a PRD as a PR.
`validate-prd.yml` — validates spec artifacts on every PR.
`prototype-guard.yml` — blocks `proto/*` branches merging to main.

Planning and implementation stay manual at every autonomy tier.

**Changing in build items 18 and 23:** implementation is to run unattended once the
plan is approved (K3), and a scheduled triage job is to apply `spec:auto` itself
(K6), both off until a project enables them. The plan stays the human gate. The
sentence above describes the code as it runs today.

## Files

`bootstrap.sh` installs from this tree. The arrow says where each part lands in the
target repository.

```
dev-flow/
├── SKILL.md                      the agent's instructions for the spec stages
├── README.md                     this file
├── GETTING-STARTED.md            step-by-step for a new repo
│                                 (these three → .claude/skills/dev-flow/)
├── commands/                     → .claude/commands/
│   ├── spec-setup.md             /spec-setup <domain> — one-time repo setup
│   ├── spec.md                   /spec — issue → prd.md
│   ├── spec-review.md            /spec-review — advisory PRD review, cannot edit
│   ├── verdict.md                /verdict — prototype result → evidence in prd.md
│   ├── plan.md                   /plan — prd.md → plan.md, then stops
│   ├── acceptance.md             /acceptance — prd.md → acceptance.md, forked context
│   ├── harness.md                /harness — acceptance.md → runnable tests, forked context
│   ├── implement.md              /implement — approved plan.md → code
│   ├── verify.md                 /verify — acceptance cases vs code, failures routed by cause
│   ├── review.md                 /review — pre-merge review against plan, PRD and coverage
│   ├── spec-check.md             /spec-check — validate every artifact
│   └── coverage.md               /coverage — requirement coverage matrix
├── hooks/                        → .claude/hooks/
│   ├── spec-validate.sh          PostToolUse: validates whichever artifact was written
│   ├── acceptance-guard.sh       PreToolUse: blocks reading acceptance.md, and the tests generated from it, while coding
│   └── integrity-guard.sh        PreToolUse: blocks --no-verify, dropped ids, and config edits while coding
├── scripts/                      → .claude/skills/dev-flow/scripts/
│   ├── bootstrap.sh              install into a repo, idempotent; --dry-run writes nothing
│   ├── settings_merge.py         merges settings.hook.json into .claude/settings.json
│   ├── settings_preflight.py     CI: fails the job before Claude runs if its settings would not load as shipped
│   ├── spec_lib.py               shared parsing, frontmatter, fingerprints
│   ├── validate_prd.py           PRD structure, evidence entries, metric sources
│   ├── validate_plan.py          task structure, REQ or issue references, seams, skipped steps
│   ├── validate_acceptance.py    case structure, freeze check, implementation leaks
│   ├── coverage.py               REQ → tasks → cases matrix
│   ├── spec-check-all.sh         batch validate: every artifact, one file, or one issue
│   ├── ac_trace.py               links test results (JUnit XML, or runner output) back to AC- ids
│   ├── evidence.py               evidence ledger: runs a flow.json check, records exit code and tree; FRESH/STALE/MISSING
│   ├── pipeline_config.py        reads and checks flow.json
│   ├── issue_envelope.py         wraps issue text as untrusted data for the spec job
│   └── retry_guard.sh            caps fix attempts at 2
├── references/                   → .claude/skills/dev-flow/references/ (domain packs)
│   ├── greenfield.md
│   └── voice-agent.md
├── assets/                       → .claude/skills/dev-flow/assets/, and:
│   ├── prd-template.md
│   ├── plan-template.md
│   ├── acceptance-template.md
│   ├── example-prd.md            a real-shaped PRD that exits 2
│   ├── github-issue-template.md  → .github/ISSUE_TEMPLATE/spec-request.md
│   ├── flow.example.json         → flow.json, when no delivery target is given
│   ├── settings.hook.json        hooks, tier-1 deny rules, env, autoMemoryEnabled → merged into .claude/settings.json
│   ├── ci-deny-settings.json     deny rules for the Claude step in spec-pipeline.yml
│   ├── validate-prd.yml          → .github/workflows/
│   ├── spec-pipeline.yml         → .github/workflows/
│   └── prototype-guard.yml       → .github/workflows/
├── tests/                        NOT installed, on purpose (see below)
│   ├── test_issue_envelope.py    fixture runner for issue_envelope.py
│   ├── check_spec_pipeline_grants.py  static check of the spec job's grants
│   ├── test_trust_check.py       fixture runner for the spec job's trust check
│   ├── check_autonomy_tiers.py   static check: two tiers, /review merges only at autonomous
│   ├── judge_review_run.py       judges a live `-p` /review run from its stream and GitHub
│   ├── run_review_proof.sh       runs that live /review proof in a scratch clone
│   ├── check_spec_setup.py       /spec-setup's pin, context lines and post-install check
│   ├── check_pocock_live.py      the pinned Pocock install, live, in a scratch project
│   ├── test_validate_plan.py     fixture runner for validate_plan.py and coverage.py
│   ├── check_bash_rule_syntax.py static check: every Bash rule in the documented space form
│   ├── probe_bash_rules_live.py  what the rules match, and that the commands still load, live
│   ├── test_settings_merge.py    fixture runner for settings_merge.py and bootstrap's --dry-run
│   ├── probe_settings_live.py    a `-p` read of .env, and of a session transcript, is denied in a bootstrapped project, live
│   ├── test_settings_preflight.py  fixture runner for settings_preflight.py and the workflow steps that run it
│   ├── judge_preflight_run.py    judges a live spec-pipeline.yml run: failed at preflight, Claude never started
│   ├── test_bootstrap_gitignore.py  the Playwright Test docs example, and bootstrap's .gitignore append
│   ├── test_guards.py            fixture tool calls for both guard hooks, every tool Claude Code offers classed; --time measures their cold runtime
│   ├── probe_guards_live.py      the guards and the /implement and /verify markers in real `-p` sessions
│   ├── probe_stage_markers_live.py  /acceptance and /harness run their checks on the cases, live (item 26)
│   ├── probe_guard_tools_live.py  the tool list Claude Code offers, and the guards on PowerShell and Monitor, live (item 27)
│   ├── test_evidence.py          fixture runner for evidence.py, and the /verify and /review lines that use it
│   ├── judge_evidence_review.py  judges a live `-p` /review run: FRESH evidence readies the PR, STALE leaves a draft
│   ├── test_ac_trace.py          fixture runner for ac_trace.py: runner outputs and JUnit reports
│   ├── test_m1_fixes.py          M1's fixes (item 29): validators, spec-validate.sh on Windows paths, the
│   │                             issue template, and the /implement, /coverage, /spec-check and /review lines
│   ├── probe_m1_fixes_live.py    those command fixes in real `-p` sessions, default mode
│   ├── probe_hidden_tests_live.py  /implement cannot read a generated acceptance test, live (item 30)
│   └── fixtures/
│       ├── ac_trace/             acceptance files, runner outputs and JUnit reports for ac_trace.py
│       ├── m1/                   PRD, plan and acceptance fixtures for test_m1_fixes.py
│       ├── issues/               ten issue fixtures (.json and .txt)
│       ├── code-review-stub/     SKILL.md standing in for Pocock's code-review
│       ├── plans/                spec directories with plan fixtures
│       ├── settings/             .claude/settings.json fixtures for the merger
│       └── guards/               cases.json: the tool calls test_guards.py feeds the guard hooks;
│                                 init-tools.json: the tool lists Claude Code reported, live
└── optional-delivery/            installed only when bootstrap is given a delivery target
    ├── README.md                 (not installed)
    ├── commands/                 deploy.md, outcome.md, rollback.md, ship.md → .claude/commands/
    ├── scripts/validate_delivery.py  → .claude/skills/dev-flow/scripts/
    └── assets/
        ├── deliver.yml           → .github/workflows/
        ├── delivery-template.md  → .claude/skills/dev-flow/assets/
        ├── flow.vercel.json      → flow.json, with the vercel target
        └── flow.docker-vps.json  → flow.json, with the docker-vps target
```

**`tests/` is deliberately not installed into target repositories.** `bootstrap.sh`
copies `scripts/`, `references/` and `assets/`, and leaves `tests/` out on purpose:
these tests check this repository's own assets — the issue envelope, the spec job's
grants and its trust check, the autonomy tiers and `/review`, `/spec-setup`'s Pocock
install, the plan validator and coverage, the Bash rule syntax, the settings
merge, the CI settings preflight, the `.gitignore` append, the two guard hooks, the
evidence ledger, the acceptance trace and M1's fixes — not anything in a project.
`check_pocock_live.py` installs, and `probe_bash_rules_live.py`,
`probe_settings_live.py`, `probe_guards_live.py`, `probe_stage_markers_live.py`,
`probe_guard_tools_live.py`, `probe_m1_fixes_live.py`, `probe_hidden_tests_live.py` and `test_settings_preflight.py --live`
run `claude -p`, so
point them only at scratch directories. Their absence from the
installer is not a bug. Run them from the harness repo root, for example
`python3 dev-flow/tests/test_issue_envelope.py`.

## Known limits

- Nothing here has met a real issue yet. That remains the only test that matters.
- The workflows have run only on private scratch repos, never on a real project.
  `spec-pipeline.yml` ran in build item 1. `validate-prd.yml`, `prototype-guard.yml`
  and `deliver.yml`'s checks ran in build item 2; `deliver.yml`'s deploy job ran only
  as far as its "not configured" stop, since there was no deploy target.
- `/review`'s hand-off to Pocock's `code-review`, with the PRD as its spec, kept the
  skill out of `specs/` in the one run it has had (build item 3, Windows): no Glob or
  Grep, and only the PRD read. That rests on the skill following its arguments; the
  acceptance guard is still the only mechanism behind it.
- `TEMPLATE_PLACEHOLDER_RE` false-positives on generics, XML, and HTML in prose.
- The evidence ledger (`.dev-flow-run/evidence.jsonl`) is a plain file. It stops a
  model claiming a result it did not produce; it does not stop a session that sets
  out to forge a record. Files git ignores (`node_modules/`, `.env`, build output)
  are not in the fingerprint, so changing one leaves evidence FRESH. A generated
  file that is not ignored changes the tree during the run, and every record is
  STALE until it is ignored; bootstrap ignores `__pycache__/`, which the
  validators create, and any other generated output is the project's to ignore. Any
  `flow.json` edit stales every record, since the file is part of the tree.
  Computing the fingerprint writes the tree's blobs into `.git/objects`, as
  `git stash create` does.
- `ac_trace.py` reads a JUnit XML report when `flow.json` sets `acceptance_junit`,
  and otherwise scrapes the runner's output as text. Scraping is crude on purpose —
  it is what keeps the flow language-agnostic — and a verdict counts only in a
  verdict position (a status mark at the start of the line, or a runner's verdict
  word at its end), so a word in a test title is never read as one. A format it does
  not know traces as MISSING, never as a pass. A runner that does not print test
  names (Playwright's `dot`, its default under `CI`) will not trace from text; give
  it a JUnit report. The report must come from the run being traced: one written
  before the run started (piped form), or more than 60 s before the saved output
  ends (`--output`), is refused.
- The freeze check warns when a PRD changed under frozen cases; it cannot tell you
  which one should move.
- Every threshold in `references/voice-agent.md` is a placeholder.
- `references/regulated-fintech.md` is unwritten, deliberately.

The guard hooks are speed bumps, not a vault. Build item 11 (see
`research/BUILD-PLAN.md` in the harness repo) closed the gaps research found in the
acceptance guard: Write and Edit were not matched, any `/verify` marker unlocked
every issue, and the marker lived in `.claude/`, where Claude Code refuses agent
writes, so outside auto mode `/verify` could never create it. Build item 26 gave
`/acceptance` and `/harness` a marker of their own, since the guard blocked the
checks they run on the cases. What remains:

- **A timed-out hook does not block.** The hooks documentation states: "A timed-out
  `command`, `http`, or `mcp_tool` hook doesn't block the tool call. The call continues
  through the normal permission flow, so don't count on a stalled hook to act as a
  gate." Source: `research/q2-claude-code-capabilities.md` §2.3 and §11.4, quoting
  `code.claude.com/docs/en/hooks`. **DR4's response is in place on Windows:** neither
  guard runs `jq` or any other program, only bash itself. Measured cold, 20 runs per
  call, each a new process started the way Claude Code starts it, on the Windows box
  (Git Bash, 2026-09-27): the acceptance guard's worst run was 0.18 s (it was 1.08 s
  with `jq`), and the integrity guard's 0.61 s, on a Write of a 200-task `plan.md`.
  Both hooks run with `"timeout": 30`, about 50 times the worst. On the Mac (build
  item 11) the worst runs were 0.014 s and 0.36 s. Build item 27 re-measured Windows
  with the PowerShell calls added (2026-09-28): 0.35 s and 0.58 s, the timeout 85 and
  52 times those. Since build item 30 every call also reads `flow.json` for
  `acceptance_tests`; re-measured on Windows with the key set (2026-09-30), the worst
  runs were 0.12 s and 0.44 s, 245 and 69 times inside the timeout. The fail-open
  itself stays: a machine stalled for 30 seconds lets
  the call through. `spec-validate.sh` has the same shape at `"timeout": 20`.
  Unattended stages do not rely on the guards (DR1 tier 2).
- **They see what a call names, not what it touches.** The acceptance guard blocks a
  call that names `acceptance.md`, or a Grep over a spec directory or `specs/` that
  could search it. A git exclusion pathspec is not a mention: `git diff -- .
  ':!specs/42-x/acceptance.md'` hides the file, and passes when every mention in the
  command is one (`:!`, `:^` or `:(exclude)`, quoted or bare, each a whole word with
  no quote, space, `$` or backtick of its own); any other mention in the same command
  still blocks (build item 28, DECISIONS.md B12). The judge of the live `/review` proof
  (`tests/judge_review_run.py`) applies the same rule, and `tests/test_guards.py` holds
  the two to one verdict on the same commands (B14). A word dressed as an exclusion and
  unwrapped by another program is not seen. It does not see a shell glob that avoids the name
  (`cat specs/42-x/a*`), `grep -r` from the repository root, a Grep with no path, or a
  script that opens the file. For the generated acceptance tests (build item 30) it
  likewise misses a shell glob (`cat src/*.acceptance.test.ts`), a Grep with no path
  or over any directory but the glob's literal one and those holding it (so every
  Grep, for a glob that starts with a wildcard: `Grep "AC-" --glob "*.ts"` from the
  root searches them), and a command that runs them without naming one, which the
  `test` command leaving them out is meant to cover (B15). The tests are locked
  with no marker at all, as `acceptance.md` is, so a `/review` sub-agent that
  Reads one is denied. The integrity guard recognises the plain ways a shell
  command writes a file (a redirection, `sed -i`, `tee`, `cp`, `mv`, `rm`, `git
  checkout`, and the like); `python -c` or a variable holding the file name get past
  it. Its list of lint and format configuration files is fixed and cross-ecosystem;
  `pyproject.toml`, `setup.cfg`, `tox.ini`, `package.json` and `tsconfig.json` are
  left off because implementing a task edits them legitimately.
- **They cover the tools Claude Code offered when last checked, and read only a
  call's input.** Build item 26 found that on Windows the `PowerShell` tool bypassed
  both guards (`Get-Content specs/42-add/acceptance.md` returned the cases while issue
  42 was being implemented). Since build item 27 both are wired to every tool the
  `-p` init event of `claude` 2.1.283 on Windows lists that can read a file, run a
  command or write one (`tests/test_guards.py`'s `TOOL_CLASSES` gives the reason for
  every tool, in or out), and the live check found the same read blocked. A tool a
  later release adds fails that test until it is classed, but only once someone
  captures a new tool list: run `tests/probe_guard_tools_live.py` (or
  `test_guards.py --init` on any saved `-p` stream) after each Claude Code upgrade, on
  each machine. The lists were captured with `--strict-mcp-config`: a project's own
  MCP servers add tools no guard sees. On macOS the list has not been captured.
- **A skill's `!` lines run unseen, so no command that reads the cases is the
  model's to run.** The Skill tool's input is the skill's name and arguments, not the
  commands its `!` lines run, so the guards see only the arguments: a call whose
  arguments name one issue's cases file (`specs/42-x/acceptance.md`) is blocked while
  that issue is locked, while the name in prose ("do not read any acceptance.md
  file") and a glob over every spec (`specs/*/acceptance.md`, which `/review` tells
  `code-review` not to read) pass (build item 28, DECISIONS.md B13). Every dev-flow command whose `!` lines read
  `acceptance.md`, or run a script that does (`/verify`, `/harness`, `/implement`,
  `/review`, `/ship`, and since build item 27 `/spec-check` and `/coverage`), is
  `disable-model-invocation: true`, and `tests/test_guards.py` fails if one is not.
  Before that, with issue 42 being implemented and `Skill` and a bare `Bash` allowed,
  the model's own `/spec-check 42` put "AC-001 'Then' is too short to be checkable:
  'it returns 5'" in the session; now the Skill call is refused and no case text
  appears (build item 27, Windows, 2.1.283). You can still type both commands. A
  skill installed later, or one of your own, with such a line is not covered: give it
  the same flag.
- **PowerShell can hide a name as a shell can.** A backtick inside a name
  (``acc`eptance.md``), a name built from strings or read from a variable, and
  `Get-ChildItem -Recurse | Get-Content` from above the spec directory are not seen,
  like the shell globs above.
- **The markers are files an agent could make by other means.** A tool call that
  creates a `verifying-` or `authoring-` marker, or touches `.dev-flow-run/` at all
  while an issue is being worked on (other than an `rm` of a `verifying-` or
  `authoring-` marker), is blocked. A script that writes one is not seen.
  `/implement <n>` puts back `implementing-<n>`, which keeps issue n locked whatever
  `verifying-` or `authoring-` marker exists.
- **A marker left behind keeps its phase on.** If `/verify` never finishes, its
  `verifying-<n>` marker leaves issue n readable, and `implementing-` or `verifying-`
  markers keep `flow.json` and the configs protected. The block message names the
  marker that put the phase on (build item 29); delete that file in `.dev-flow-run/`
  yourself. Likewise an `/acceptance` or `/harness`
  run that stops before its last step leaves `authoring-<n>`, and issue n readable,
  until `/implement <n>` or `/verify <n>` removes it.
- **Markers belong to one working tree.** The hooks look for `.dev-flow-run/` at the
  root of the git working tree the call runs in, which follows a `cd`. A session
  started in a worktree (`claude -w`) has its own; a session that enters one midway
  keeps `$CLAUDE_PROJECT_DIR` at the main checkout while its calls run in the
  worktree. Which tree the marker should live in when `/implement` and `/verify` run
  in different ones is build item 18's decision (DECISIONS.md B5).
- **A project wired before build item 11 keeps the old guard.** Its settings entry
  still matches `Read|Grep|Glob|Bash` with a 10-second timeout until
  `bootstrap.sh --update-hooks` is run; bootstrap and the CI settings preflight both
  warn. `--update-hooks` changes only settings entries: bootstrap never overwrites a
  file it copied earlier, so the old `acceptance-guard.sh` (which reads the old
  `.claude/spec-pipeline/` marker and runs `jq`) and the old `verify.md` stay. The old
  script with the new matcher would block `/acceptance`'s own Write. The same goes for
  a project wired before build item 26: its guards do not know the `authoring-` marker,
  so they block `/acceptance`'s validator and `/harness`'s trace. A project wired before
  build item 27 keeps matchers without `PowerShell`, `Monitor`, `NotebookEdit` and
  `Skill` until `--update-hooks`, and guard scripts that do not read them. One wired
  before build item 30 keeps guards that do not read `acceptance_tests`, and a
  `/harness` that does not write to it. One wired
  before build item 28 keeps the guard that blocks exclusion pathspecs and a Skill
  call's prose, and a `/spec-setup` that repairs with the installed `bootstrap.sh`,
  which stops halfway. To upgrade, delete
  `.claude/hooks/acceptance-guard.sh`, `.claude/hooks/integrity-guard.sh` and
  `.claude/commands/` `verify.md`, `implement.md`, `acceptance.md`, `harness.md` and
  `spec-setup.md`, and `.claude/skills/dev-flow/scripts/pipeline_config.py` (after saving any edits of your own), then run
  `bootstrap.sh --update-hooks`: it copies the new ones.

The fifth weakness research found was auto memory. Build item 6 answered it as far
as a setting can:

- **Auto memory: switched off, not every route closed.** Claude Code's auto memory is
  on by default. Each repository has one memory directory at
  `~/.claude/projects/<project>/memory/`, shared by all its worktrees, and its
  `MEMORY.md` is loaded into every session. Session-start injection is not a tool call,
  so no `PreToolUse` hook fires for it, and a memory write goes to a path outside the
  project that the guard's matcher does not cover. Source:
  `research/q2-claude-code-capabilities.md` §3.2, §3.5 and §11.2, quoting
  `code.claude.com/docs/en/memory`. **Since build item 6, bootstrap writes
  `"autoMemoryEnabled": false`** (DR2). **DR2 does not cover these, and does not claim to:**
  - `--continue` and `--resume` carry the whole earlier conversation, whatever the
    setting says.
  - What a sub-agent hands back to its parent is a separate route, and it is
    undocumented.
  - The setting is only as good as the settings that load. `.claude/settings.local.json`
    and managed settings outrank the project file, and bootstrap only warns about the
    local file. A run with `--setting-sources` that leaves out `project` loads none of
    it, and neither do `--bare` or `--safe-mode`. A `-p` run silently ignores a project
    file that fails validation, and drops the whole file, not the bad key. In CI,
    `spec-pipeline.yml`'s settings preflight (`scripts/settings_preflight.py`, build
    item 7) fails the job before Claude starts instead. Interactively nothing checks
    it; `claude doctor` lists invalid settings files.
  - It holds in the projects bootstrap sets up. The harness repo, where the pipeline is
    built, keeps no hidden cases and is not covered.
  - It says nothing about whether Claude would ever have written acceptance content to
    memory. That question is moot in practice and stays unverified. An empty memory
    directory after a real run shows that the switch took effect, nothing more.

The tier-1 deny rules (under Enforced boundaries) have limits of their own. Build
item 6 measured them once, on Windows with Claude Code 2.1.283: a `-p` Read of
`.env`, and a `cat .env` that `--allowedTools` allowed, were both denied. The rest
below is from the documentation (`research/q2-claude-code-capabilities.md` §10.3,
§10.5):

- **They are not a sandbox.** Read and Edit deny rules cover Claude's file tools, the
  shell file commands Claude Code recognises (`cat`, `head`, `tail`, `sed`, `tee`) and
  redirections. They do not cover a command that reads without naming the file
  (`grep -r … .` from the directory above), a script that opens the file itself, or
  `NotebookEdit`. A Bash line the permission checker cannot analyse (`eval`, `env -C`)
  prompts instead of being denied, which in a headless run means it does not run.
  This area changed four times between Claude Code 2.1.268 and 2.1.278, so re-check it
  at each upgrade. Only the sandbox (DR1 tier 2, unattended runs) reaches every process.
- **`.env` means `.env` and `.env.<anything>`.** `.env.example` is denied too, and
  `.envrc` is not.
- **They cost friction.** Occasional denials land on files that only look like
  secrets. `Edit(.github/workflows/**)` also stops you from editing a workflow through
  Claude in an interactive session; edit it yourself.
- **Relative rules anchor to the working directory.** `**/.env` covers every `.env`
  under the directory Claude was started in, not above it.
- **The session transcripts: a route the first real run found, closed by a rule.**
  Claude Code keeps every session as `~/.claude/projects/<project>/<session>.jsonl`,
  with its sub-agents' transcripts beside it, outside the project. The acceptance
  guard looks for `acceptance.md`, so it never saw them, and no rule covered them
  before build item 31. After the first real run (build item 10) eight of them held
  case titles and Given/When/Then text: the `/acceptance`, `/harness` and `/verify`
  sessions and their sub-agents. Nothing loads a transcript into a later session, but
  an `/implement` that read one would have had the cases. Without the rule, a
  default-mode Read there waits for an approval a headless run never gets, but an
  allow (`--allowedTools`) lets it through, and in auto mode with this Windows box's
  user settings a Read of a transcript succeeded with no allow at all.
  `Read(~/.claude/projects/**)` (DECISIONS.md B18) closes it. Build item 31 measured
  it on Windows with Claude Code 2.1.285 (`tests/probe_settings_live.py`): a Read of
  a real transcript, and a `cat` of it by `~/` and by absolute path with `Bash(cat *)`
  allowed, were all denied by the rule, with project settings only in `default` mode
  and with every settings source; so was a Read that `--allowedTools` allowed. Claude
  Code still started and wrote each session's transcript with the rule in place. The
  Mac was not measured. What it does not cover:
  - A script that opens a transcript, and a command the permission checker does not
    read paths from, as for the other rules. A `Get-Content` by the Windows
    `PowerShell` tool was not tried.
  - Transcripts somewhere else. The rule names `~/.claude` only, so a machine that
    sets `CLAUDE_CONFIG_DIR` to move Claude Code's directory is not covered (the
    probe refuses to run there).
  - **Its cost:** the same directory holds the file Claude Code saves a tool output
    to when it is too large to show (`<session>/tool-results/`). The session sees a
    2 KB preview and is told where the rest is, but cannot read it: in build item 31 a
    Read of the saved output of a 210 KB `cat` was denied by the rule. Filter such a
    command's output instead (`… | tail -n 50`). The memory directory
    is under it too, which is moot while auto memory is off.
