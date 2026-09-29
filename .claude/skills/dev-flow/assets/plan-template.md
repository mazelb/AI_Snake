---
title: <same title as the PRD>
issue: <owner/repo#123>
prd: specs/<n>-<slug>/prd.md
owner: <github handle>
status: draft
created: <YYYY-MM-DD>
---

# Plan — <title>

## Approach

<Three to eight sentences on how this gets built. Name the real modules and
services. This is where the decomposition strategy lives, not the task list.>

## Skipped steps

<Write "None." when every step runs. Otherwise one line per skipped step, in the
form "- prd: why" or "- acceptance: why"; nothing else can be skipped, and a skip
with no reason fails validation. Approving this plan approves each skip. Skipping
the PRD means every task cites this plan's issue instead ("Satisfies: #123"),
`prd:` above is "none", and there are no acceptance cases, so no /verify evidence.>

## Tasks

### TASK-001 <short imperative name>

- Satisfies: REQ-001
- Touches: <path/to/module>, <path/to/other>
- Seams: <where this task's tests attach — a function, endpoint or module boundary>
- Done when: <observable condition — a test passes, an endpoint returns, a flag exists>

<One to three sentences on what this task actually changes. Not a restatement of
the requirement — the requirement says what must be true, the task says what to do.>

### TASK-002 <short imperative name>

- Satisfies: REQ-001, REQ-002
- Touches: <path>
- Seams: none — <why this task has nothing to test at, e.g. config or docs only>
- Done when: <observable condition>

<description>

## Sequencing

<Which tasks block which. Say what can run in parallel. If everything is strictly
sequential, say that too — it is a scheduling fact worth knowing before starting.>

## Out of scope

- <Something a reasonable implementer might otherwise pick up along the way>

## Risks

<Where this plan is most likely to be wrong. If nothing here worries you, the plan
is either trivial or under-examined.>
