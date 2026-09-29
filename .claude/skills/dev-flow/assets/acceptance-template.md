---
title: <same title as the PRD>
issue: <owner/repo#123>
prd: specs/<n>-<slug>/prd.md
prd_fingerprint: <sha256 of prd.md at generation — written by /acceptance>
status: frozen
created: <YYYY-MM-DD>
---

# Acceptance — <title>

These cases are derived from the PRD, before implementation exists, and are frozen
once written. They describe what the requirement demands, never what the code does.

## AC-001 [REQ-001] <short name>

- Type: automated | manual
- Given: <starting state>
- When: <the action or event>
- Then: <the observable outcome, with its number or exact state>
- Fails if: <the specific wrong behaviour this case is designed to catch>

## AC-002 [REQ-001] <short name>

- Type: automated | manual
- Given: <starting state>
- When: <the action or event>
- Then: <observable outcome>
- Fails if: <wrong behaviour>

## Not covered

<Requirements this file deliberately does not verify, and why — usually because
verification needs infrastructure that does not exist yet. Naming the hole is the
point; an untested requirement that nobody has noticed is the failure mode.>
