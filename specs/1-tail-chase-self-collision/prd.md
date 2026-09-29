---
title: Let the snake's head enter the cell its tail vacates on the same tick
issue: mazelb/AI_Snake#1
owner: mazelb
status: draft
created: 2026-09-29
domain: greenfield
---

# Let the snake's head enter the cell its tail vacates on the same tick

## Problem

The game ends when the snake's head moves into the cell its own tail is leaving on
that same tick. In `App.tsx`, `gameLoop` runs the "Check Self Collision" block
(`snake.some(s => s.x === newHead.x && s.y === newHead.y)`) against the *current*
snake, including its last segment, before the food check decides whether the tail
is popped (`newSnake.pop()`). On a tick with no food eaten the tail cell is free by
the time the head arrives, but the game still reports GAME OVER. With
`INITIAL_SNAKE` at length 3 (`constants.ts`), this first bites after one food is
eaten (length 4), e.g. when the player turns in a tight 2×2 loop.

## Affected users

Anyone playing Neon Snake. Per the issue, this is a hobby project with no tracked
player numbers — in practice the owner and whoever they share it with. The bug
appears once the snake is at least 4 segments long and the player turns tightly.

## Success metric

- Metric: number of the self-collision scenarios in REQ-001–REQ-002 covered by a passing automated test
- Current baseline: 0 of 2 — the repo has no test files (vitest is a dev dependency since 0ba4d11)
- Target: 2 of 2
- Source: vitest run output

## Non-goals

- No change to boundary collisions (`GRID_SIZE` bounds check) or level-wall collisions (`level.walls`).
- No change to speed (`INITIAL_SPEED`, `MIN_SPEED`, `SPEED_DECREMENT`), scoring, or high score handling.
- No change to Gemini level generation.
- No visual or UI changes, including `components/Grid.tsx` body rendering.
- Not fixing the local blank page (`index.html` has no entry script) — a separate issue.
- Not fixing the food-spawn fallback to (0,0) when no free cell is found.

## Requirements

### REQ-001 [P0] Head may enter the vacating tail cell

On a tick where the snake does not eat, the head moving into the cell occupied by
the snake's last segment does not end the game.

**Acceptance:** Given a snake of length ≥ 4 whose next head position equals its
last segment's position and is not the food cell, one game tick leaves the status
PLAYING, and the resulting snake has the same length with the head at that cell.
Covered by an automated test.

### REQ-002 [P0] Any other body segment is still fatal

The head moving into any body segment other than the last one ends the game.

**Acceptance:** Given a snake whose next head position equals a segment at any
index from 1 to length−2, one game tick sets the status to GAME_OVER. Covered by an
automated test.

### REQ-003 [P0] [WITHDRAWN] Tail cell is fatal on an eating tick

Withdrawn 2026-09-29 by mazelb: food never spawns on a snake cell, so this case cannot occur in play.

On a tick where the snake eats (so the tail does not move), the head moving into
the last segment's cell ends the game.

**Acceptance:** Given a snake whose next head position equals its last segment's
position and also equals the food position, one game tick sets the status to
GAME_OVER. Covered by an automated test.

## Constraints

- No new runtime dependencies: the app runs in AI Studio from the import map in `index.html`, which pins only `react`, `react-dom` and `@google/genai` (source: issue #1).
- Stay on React 19, Vite 6, TypeScript 5.8 (source: `package.json`).
- `npx tsc --noEmit` must keep passing (source: issue #1).
- Tests use vitest, already in `devDependencies` (source: `package.json`, commit 0ba4d11).

## Evidence

## Open questions

| Question | Owner | Blocks |
|---|---|---|
| None | — | — |

Answered 2026-09-29 by mazelb:

- Extracting the collision logic from `gameLoop` into a pure function, so vitest can test it without rendering, is acceptable; it is not a UI change.
- The food cell can never coincide with the tail cell in play, so REQ-003 is withdrawn.
