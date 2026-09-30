---
title: Always place food on a free cell
issue: mazelb/AI_Snake#4
owner: mazelb
status: draft
created: 2026-09-30
domain: greenfield
---

# Always place food on a free cell

## Problem

Food can appear on top of the snake or on a level wall. `getRandomPoint` in
`App.tsx` draws up to 1000 random cells on the `GRID_SIZE` × `GRID_SIZE` grid
(`constants.ts`) and, if none is free of the snake and the level walls, returns
`{ x: 0, y: 0 }` without checking it. On a long snake or a dense Gemini level
(`services/geminiService.ts`) the random draws can all miss the few remaining free
cells, and the food lands on (0,0) even when that cell is snake or wall. Food on a
wall can never be eaten; food under the snake's body is invisible.

## Affected users

Anyone playing Neon Snake. Per the issue, this is a hobby project with no tracked
player numbers — in practice the owner and whoever they share it with. It shows up
late in a long game or on dense generated levels.

## Success metric

- Metric: number of the food-placement scenarios in REQ-001–REQ-002 covered by a passing automated test
- Current baseline: 0 of 2 — `getRandomPoint` has no test and is not in `gameLogic.ts`
- Target: 2 of 2
- Source: vitest run output

## Non-goals

- Not defining what happens when no free cell is left at all (a "board full" win); that is a separate decision.
- No change to movement, collision, speed, scoring, or high score handling (`advanceSnake` in `gameLogic.ts` is untouched).
- No change to Gemini level generation.
- No visual or UI changes.

## Requirements

### REQ-001 [P0] Food lands on a free cell whenever one exists

When at least one cell is free of the snake and the walls, the food position chosen
is always such a cell, regardless of what the random source returns.

**Acceptance:** Given a snake and walls that leave exactly one free cell, and a
random source that would pick an occupied cell on every draw, the chosen food
position equals the free cell. Given the same setup with a different single free
cell, the result is that cell. Covered by an automated test.

### REQ-002 [P0] Every food placement uses that rule

The food placed after eating, at game start or reset, and after a level is
generated is chosen by the same rule as REQ-001, with no fallback to (0,0).

**Acceptance:** In `App.tsx`, the three places that set food after a tick that
ate, in `resetGame`, and in `handleGenerateLevel` all obtain the position from the
REQ-001 function, and no code path returns `{ x: 0, y: 0 }` as a default. Checked
by the REQ-001 tests plus a search of `App.tsx` showing no remaining fallback.

## Constraints

- No new runtime dependencies: the app runs in AI Studio from the import map in `index.html` (source: issue #4).
- Stay on React 19, Vite 6, TypeScript 5.8 (source: issue #4, `package.json`).
- `npx tsc --noEmit` must keep passing (source: issue #4).
- Tests use vitest; tick rules already live in `gameLogic.ts` (source: issue #4, issue #2). Moving the placement logic there so it can be tested without rendering is assumed acceptable, as confirmed for the same move in `specs/1-tail-chase-self-collision/prd.md`.

## Evidence

## Open questions

| Question | Owner | Blocks |
|---|---|---|
| When no cell is free, what should the function return or do? Out of scope here, but the function still needs some defined result. | mazelb | plan |
