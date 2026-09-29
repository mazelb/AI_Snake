---
title: Recover the session when connectivity drops mid-conversation
issue: aabsi/rafiq#14
owner: melbawab
status: draft
created: 2026-08-26
domain: voice-agent
---

# Recover the session when connectivity drops mid-conversation

## Problem

Users lose the conversation entirely when the network drops. Rafiq is used on the
move and in crowds, where connectivity is intermittent by default rather than by
exception. Today the agent goes silent with no indication of what happened, and
the user has no way to tell whether it is thinking, broken, or offline.

## Affected users

Anyone using the app away from stable wifi, which is the primary intended usage
context. [NEEDS INPUT: observed drop rate during a session — needs a source]

## Success metric

- Metric: share of sessions that resume after a connectivity drop rather than being abandoned
- Current baseline: none — no resume path exists today
- Target: 70% of sessions interrupted by a drop under 60s are resumed by the user
- Source: [NEEDS INPUT: session event stream — does not exist yet, may be REQ-004]

## Non-goals

- Full offline operation of the agent; this covers interruption and resume only
- Queuing and replaying user utterances captured while offline
- Any change to the ASR or TTS providers

## Constraints

- Session state must not retain raw audio off-device, per the retention position
  recorded in docs/adr/0003-audio-retention.md
- Resume must work without re-authentication within the session window

## Requirements

### REQ-001 [P0] Surface the offline state audibly and visually

When the network becomes unavailable mid-conversation, the agent tells the user
what happened rather than going silent.

**Acceptance:** With the network disabled mid-turn, the app surfaces an offline indicator and an audible cue within 2s of the failed request.

### REQ-002 [P0] Preserve session state across a drop

Conversation state survives the interruption so the user returns to where they
were rather than to a fresh session.

**Acceptance:** After a 60s disconnection, reconnecting restores the prior turn history and the agent's pending context, verified across 10 simulated drops.

### REQ-003 [P1] Resume without losing the in-flight turn

The turn that was in progress when the drop occurred is either completed or
explicitly discarded, never left ambiguous.

**Acceptance:** On reconnect, the in-flight turn either produces its response or the agent states that it did not complete, in every one of 10 simulated drops.

## Open questions

| Question | Owner | Blocks |
|---|---|---|
| How long should the session window stay resumable? | melbawab | REQ-002 |
| Do we need a session event stream before we can measure this at all? | melbawab | metric |
