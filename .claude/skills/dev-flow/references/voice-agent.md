# Domain pack: voice agents

Apply this when the work touches speech in or speech out — ASR, TTS, streaming
inference, turn-taking, or an agent a user talks to rather than types at.

The defining constraint is that latency is a product feature, not an engineering
detail. A voice agent that is correct but slow is worse than a text agent, because
the user is standing there in silence with no cursor to look at. Every requirement
in this domain is implicitly a latency requirement.

> This pack contains the questions, not the answers. The thresholds below are
> placeholders — replace them with your own measured budgets once you have them.
> Do not let a PRD inherit a number from this file as if it were grounded.

## Ask these before writing the PRD

**Latency budget**
- What is the end-to-end target from user stops speaking to agent starts speaking?
  State it as p95, not average — averages hide the failures people remember.
- How does the budget split across the hops: endpointing, ASR, retrieval or tool
  calls, LLM first token, TTS first byte, network? A change that adds 200ms
  somewhere must say which hop it spends it in and what it takes it from.
- Is there a filler or acknowledgement strategy covering the gap, and does this
  change affect it?

**Turn-taking**
- How is end-of-speech detected, and what happens on a false endpoint mid-sentence?
- Can the user interrupt (barge-in)? What happens to in-flight TTS and to the
  partial LLM response when they do?
- What happens on simultaneous speech, or on a long silence?

**Speech recognition reality**
- Which languages and which varieties? For Rafiq specifically: MSA is not the same
  target as Egyptian, Gulf, or Levantine dialect, and a spec that says "Arabic"
  has not made a decision. Code-switching mid-utterance is normal for this user
  base and needs an explicit position.
- What is the acceptable word error rate, measured on what audio? Clean-room WER
  is not the number that matters if users are outdoors, in crowds, or on speaker.
- Domain vocabulary: proper nouns, ritual and religious terms, place names. These
  are where generic ASR fails hardest and where a custom vocabulary or biasing
  list becomes a requirement with an ID.

**Failure and fallback**
- What does the agent do when ASR returns low confidence — ask again, guess, or
  fall back to text or buttons?
- What happens with no connectivity, or degraded connectivity? For a companion
  app used while travelling or in crowds, offline behaviour is a first-class
  requirement, not a graceful extra.
- Is there a path to a human, or to a deterministic non-agent flow, when the
  agent cannot proceed?

**Cost**
- Cost per minute of conversation, broken out by ASR, LLM, and TTS. Voice
  economics are per-minute rather than per-request, which means an engagement
  win can be a margin loss. Any requirement that lengthens conversations should
  state its cost effect.
- Which parts run on device versus in the cloud, and does this change move that
  line?

**Privacy and retention**
- Is raw audio retained, and for how long? Voice is biometric data in several
  jurisdictions and the answer belongs in Constraints with its source named.
- Is the user told they are being recorded, and where does that live in the flow?

**Evaluation**
- How will you know this worked, given that "the agent answered well" is not
  directly measurable? Usable proxies: task completion rate, turns to completion,
  barge-in rate, fallback rate, abandonment mid-conversation. Pick one and name
  where it is read from.
- Is there a held-out set of real utterances to evaluate against? If not, building
  one is a requirement, not a preliminary.

## Requirements this domain usually needs

- A latency requirement naming the hop, the percentile, and the measurement point
- A fallback requirement for low-confidence recognition
- A degraded-connectivity or offline requirement
- A language and dialect coverage requirement, stated per variety
- A cost-per-minute ceiling when the change affects conversation length or model choice
- A retention and disclosure requirement when audio leaves the device

## Acceptance conditions that work here

Prefer: **measured signal + percentile + condition + corpus.**

- Weak: "responses feel fast enough"
- Strong: "p95 from end-of-speech to first TTS byte stays under [X]ms on the
  [named] evaluation set over [N] conversations"

- Weak: "handles Arabic well"
- Strong: "WER on the [named] dialect evaluation set stays at or below [X]% with
  no regression on MSA"

- Weak: "works when the network is bad"
- Strong: "with the network disabled mid-conversation, the agent surfaces the
  offline state within 2s and preserves the session for resume"

## Browser-level acceptance

When the agent has a web client, Playwright Test can run the conditions that are
visible in the page, unattended. Set it up as in `GETTING-STARTED.md` step 3b; in
`flow.json`:

```json
"acceptance": "npx playwright test --grep @AC-"
```

Each test title starts with its case id, with the `@` the grep selects on. The
degraded-connectivity condition above, for example:

```ts
test('@AC-004 offline state surfaces within 2s and the session resumes', async ({ page, context }) => {
  await page.goto('/talk');
  // start a conversation, then drop the network mid-turn
  await context.setOffline(true);
  await expect(page.getByText('You are offline')).toBeVisible({ timeout: 2_000 });
  await context.setOffline(false);
  // assert the same session id is still shown
});
```

It runs in `chromium`, headless, in a fresh context with no browser profile or
saved session. A browser test reads the page, not the audio: latency percentiles
and WER come from the evaluation set and the telemetry named in the PRD, not from
here. To drive the microphone with a recorded utterance instead of a person,
Chromium takes `--use-fake-ui-for-media-stream`, `--use-fake-device-for-media-stream`
and `--use-file-for-fake-audio-capture=<file.wav>` as launch arguments
(`launchOptions.args` in the project's `use`); keep that file in the repo, never a
real user's recording.
