<!--
Save as .github/ISSUE_TEMPLATE/spec-request.md

This template is part of the PRD pipeline, not upstream of it. The skill reads
these fields as its minimum payload and refuses to generate a PRD when two or
more are missing — a thin issue produces a fluent, confident, fabricated PRD.
-->
---
name: Spec request
about: Work agreed in ideation that should be specced before implementation
labels: ["spec:auto"]
---

## What problem are we solving

<!-- Observable behaviour today, not the feature you have in mind. -->

## Who is affected

<!-- Which users, roughly how many. "Everyone" is almost never true. -->

## How would we know it worked

<!-- Any signal, even rough. A metric name with no number is still useful here —
     the PRD stage will chase the baseline. -->

## What are we explicitly not doing

<!-- At least one boundary. This is the field that prevents scope drift later,
     and the one most often left blank. -->

## Hard constraints

<!-- Deadlines that are real, platform limits, compliance requirements,
     upstream dependencies. Name the source of each. -->

## Domain

<!-- one of: voice-agent | greenfield | regulated-fintech | general -->

## Links

<!-- Design docs, prior specs, dashboards, related issues. -->
