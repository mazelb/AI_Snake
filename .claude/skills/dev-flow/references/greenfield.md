# Domain pack: greenfield

Apply this when the project has no users yet — a new repo, a new product, a side
venture at first commit.

The defining constraint is that you have no baselines and no telemetry, which means
almost every requirement is a hypothesis wearing a requirement's clothes. The job of
a greenfield PRD is not to be certain. It is to be *falsifiable*: to state what you
believe, what would prove you wrong, and how little you can build to find out.

## Ask these before writing the PRD

**What is actually being tested**
- What belief does this work exist to test? Name it in one sentence.
- What result would make you stop or change direction? If no result would, this is
  not a test and the PRD should say so plainly — building because you have decided
  to build is legitimate, but it should be an explicit choice.
- What is the smallest thing that produces that signal? Greenfield PRDs bloat
  because nothing is pushing back on scope; the non-goals section is doing more
  work here than in any other domain.

**Metrics without history**
- There is no baseline. Write `Current baseline: none — new product` rather than
  a fabricated number or a `[NEEDS INPUT]` marker, since no human can supply it either.
- The target is still a number, and it is still worth setting. A guessed target
  you write down and later miss teaches you something; an unstated target teaches
  you nothing. Frame it as a threshold that would justify continuing: "12 of 20
  test users complete a full session unaided."
- Name where the number comes from even if that source does not exist yet. If the
  answer is "nowhere," building the measurement is requirement REQ-001.

**Reversibility over correctness**
- Which decisions here are hard to undo later — data model, auth model, hosting,
  a third-party dependency at the core, anything that touches money or user data?
  Those deserve the spec time.
- Which are trivially reversible? Those should be decided in code, not in the PRD.
  A greenfield PRD that specifies component structure is spending its budget in
  the wrong place.

**Scope discipline**
- What are you deliberately not building yet, even though it obviously belongs in
  the product eventually? Auth, billing, admin, onboarding, and settings are the
  usual suspects — list the ones being deferred by name.
- What are you willing to do manually for the first N users? Manual is a valid
  answer and it belongs in the PRD so nobody quietly automates it.

**Throwaway status**
- Is this code meant to survive? Say so. A prototype that is honestly labelled a
  prototype can skip requirements that production code cannot, and the label
  prevents it from silently becoming the foundation.

## How this changes the template

- `Affected users` becomes *intended* users, stated as a hypothesis with the
  evidence you have — a conversation, a waitlist, your own experience of the
  problem. "No evidence yet" is an acceptable and useful answer.
- `Success metric` keeps its number but the source may be a thing you are building.
- `Non-goals` should be the longest section in the document. If it is not, the
  scope is not yet under control.
- `Open questions` will outnumber requirements at this stage. That is correct.

## Acceptance conditions that work here

Prefer conditions observable by a human in a session, since there is no telemetry:

- Weak: "users can complete the core flow"
- Strong: "a first-time user completes [named flow] end to end without assistance
  in under 3 minutes, observed across 5 sessions"

- Weak: "the data model supports future features"
- Strong: "adding a second [entity type] requires no migration of existing rows,
  demonstrated by a test that inserts one"

## Browser-level acceptance

When the product has a web UI, the strong conditions above are usually a browser
session, and Playwright Test can run them unattended. Set it up as in
`GETTING-STARTED.md` step 3b; in `flow.json`:

```json
"acceptance": "npx playwright test --grep @AC-"
```

Each test title starts with its case id, with the `@` the grep selects on:

```ts
test('@AC-001 a first-time user completes sign-up end to end unaided', async ({ page }) => {
  const started = Date.now();
  await page.goto('/');
  // the named flow, step by step, with no help text opened
  await expect(page.getByRole('heading', { name: 'Welcome' })).toBeVisible();
  expect(Date.now() - started).toBeLessThan(3 * 60_000);
});
```

It runs in `chromium`, headless, in a fresh context with no browser profile or
saved session. What stays manual is the part a script cannot observe: "without
assistance, across 5 sessions" is still a human watching people, so keep that
half of a condition as a `Type: manual` case rather than weakening it to fit a
test.
