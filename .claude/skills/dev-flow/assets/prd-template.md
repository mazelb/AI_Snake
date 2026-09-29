---
title: <short imperative title, e.g. "Reduce cold-start time on session join">
issue: <owner/repo#123>
owner: <github handle of the human accountable for this PRD>
status: draft
created: <YYYY-MM-DD>
domain: <voice-agent | greenfield | regulated-fintech | general>
---

# <title>

## Problem

<What is wrong today, stated in terms of observable behaviour rather than a missing
feature. Two to five sentences. If you cannot describe the problem without naming
the solution, the problem is not understood yet — raise it as an open question.>

## Affected users

<Who experiences this, and roughly how many or what proportion. Segment if the
impact is uneven. Use [NEEDS INPUT: ...] rather than estimating.>

## Success metric

- Metric: <the single number that moves if this works>
- Current baseline: <value, or [NEEDS INPUT: ...]. For a greenfield project write
  "none — new product"; nobody can supply a baseline that does not exist.>
- Target: <value with a number in it>
- Source: <the dashboard, telemetry event, or query this is read from>

<One metric. If a second one is genuinely required, add it as a second block —
but a PRD with four success metrics usually has none.>

## Non-goals

- <Something a reasonable reader would otherwise assume is in scope>
- <A tempting adjacent problem being deliberately left alone>

## Requirements

### REQ-001 [P0] <short name>

<What the system must do, in one or two sentences. One requirement per behaviour —
if the statement contains "and", check whether it is really two requirements.>

**Acceptance:** <An observable condition someone could check without asking the
author what it meant. Include the number, the threshold, or the exact state change.>

### REQ-002 [P1] <short name>

<statement>

**Acceptance:** <observable condition>

## Constraints

<Hard boundaries this work must respect: platform limits, certification or release
windows, compliance requirements, upstream dependencies, deadlines that are real.
Name the source of each constraint. A constraint with no source is a preference.>

## Evidence

<Empty is fine on a first draft. Each entry records a question that was settled by
building something rather than by discussing it — the prototype is a primary
source, and this is where its verdict enters the spec.>

- Question: <what was unresolved>
  Verdict: <what was learned, with the number or the observed behaviour>
  Prototype: <branch name, e.g. proto/14-state-model>
  Date: <YYYY-MM-DD>

## Open questions

| Question | Owner | Blocks |
|---|---|---|
| <specific, answerable question> | <handle> | <REQ-00x, or "plan"> |
