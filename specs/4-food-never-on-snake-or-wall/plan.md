---
title: Always place food on a free cell
issue: mazelb/AI_Snake#4
prd: specs/4-food-never-on-snake-or-wall/prd.md
owner: mazelb
status: approved
created: 2026-09-30
---

# Plan — Always place food on a free cell

## Approach

The bug comes from rejection sampling. `getRandomPoint` in `App.tsx` keeps drawing
random cells and gives up after 1000 misses. The fix replaces sampling with
enumeration. A new pure function `placeFood(snake, walls, random = Math.random)` in
`gameLogic.ts`, next to `advanceSnake`, walks the `GRID_SIZE` × `GRID_SIZE` grid,
collects every cell that is neither snake nor wall, and indexes that list with
`Math.floor(random() * free.length)`. Every value in `[0, 1)` then lands on a free
cell, so REQ-001 holds no matter what the random source returns. An empty list is
the full-board case. The function returns an outcome shaped like `TickOutcome`:
`{ status: GameStatus.PLAYING, food: Point }` or
`{ status: GameStatus.GAME_OVER, food: null }`. REQ-003 can then be tested on the
return value, with no rendering. `App.tsx` deletes `getRandomPoint` and sends its
three food placements (after an eating tick, in `resetGame`, in
`handleGenerateLevel`) through one small helper. The helper sets the food, or calls
`handleGameOver` when the board is full.

## Skipped steps

None.

## Tasks

### TASK-001 Add placeFood to gameLogic.ts, choosing from the list of free cells

- Satisfies: REQ-001, REQ-003
- Touches: gameLogic.ts, gameLogic.test.ts
- Seams: `placeFood(snake, walls, random)` exported from `gameLogic.ts`. The random source is a parameter, so tests pass a stub such as `() => 0` or `() => 0.999999`.
- Done when: `npx vitest run` passes with new `gameLogic.test.ts` cases. (a) Snake plus walls leave one free cell; with stubs `() => 0`, `() => 0.5` and `() => 0.999999`, the result is `status: PLAYING` with `food` equal to that cell. The same holds for a second setup with a different single free cell. (b) Snake plus walls cover all 400 cells; the result is `{ status: GAME_OVER, food: null }`. (c) On an empty board, `() => 0` returns `(0,0)` and `() => 0.999999` returns `(19,19)`, which pins the indexing order. `npx tsc --noEmit` passes.

Export a `FoodPlacement` type and `placeFood`. Build an occupied-cell set keyed by
`x,y` from snake and walls. Scan rows then columns into a `free` array, and pick
by index. Reuse the existing `samePoint`/`GRID_SIZE` imports; add no dependency.
Leave `advanceSnake` untouched.

### TASK-002 Route every food placement in App.tsx through placeFood and remove getRandomPoint

- Satisfies: REQ-002, REQ-003
- Touches: App.tsx
- Seams: none. The wiring lives in React handlers that no test renders (no jsdom or testing library in the repo, and adding them would be new dev dependencies). The behaviour at the seam is covered by TASK-001. This task is checked by `tsc` and by searching `App.tsx`.
- Done when: `getRandomPoint` and its `{ x: 0, y: 0 }` fallback are gone from `App.tsx`. Searching `App.tsx` for `getRandomPoint` and `x: 0, y: 0` finds nothing. `gameLoop`, `resetGame` and `handleGenerateLevel` each get food from `placeFood`. `gameLoop`'s dependency array no longer lists `getRandomPoint`. `npx tsc --noEmit` and `npx vitest run` pass.

Add one local helper, `spawnFood(snake, walls)`. It calls `placeFood` and then
either calls `setFood(outcome.food)` or calls `handleGameOver()`, and it tells the
caller which of the two happened. `resetGame` must not overwrite GAME_OVER with its
trailing `setStatus(IDLE)`. `handleGenerateLevel` has a `finally` that always sets
IDLE; it must skip that when placement ended the game. The eating branch of
`gameLoop` still calls `setSnake(outcome.snake)` when the board fills, so the final
full board is what the player sees.

### TASK-003 Place food once after level generation, against the new level's walls

- Satisfies: REQ-005, REQ-003
- Touches: App.tsx, gameLogic.ts, gameLogic.test.ts
- Seams: `placeFoodForNewLevel(startSnake, walls, random)` exported from `gameLogic.ts`: given the start snake and the new level's walls, it returns the placement for a fresh game (the same `FoodPlacement` shape as `placeFood`), drawing from `random` once per placement as `placeFood` does. `handleGenerateLevel` uses its result directly.
- Done when: `handleGenerateLevel` places food exactly once, from the new level's walls; `resetGame` no longer places food against a stale `level.walls`. Tests at the seam: a new level whose walls leave cells free gets food on a free cell of the new level; a new level whose walls cover every cell gives GAME_OVER. `npx tsc --noEmit` and `npx vitest run` pass.

### TASK-004 Count the final tick's points in the high score

- Satisfies: REQ-004
- Touches: App.tsx, gameLogic.ts, gameLogic.test.ts
- Seams: `highScoreAfterTick(scoreBeforeTick, pointsEarnedOnTick, highScore)` exported from `gameLogic.ts`: it returns the new high score. `handleGameOver` uses it with the tick's final score, not the stale closure value.
- Done when: tests at the seam show 90 + 10 against 95 gives 100, and a lower final score keeps the old high score; `gameLoop` passes the final score to the game-over path on both a collision and a full board. `npx tsc --noEmit` and `npx vitest run` pass.

## Sequencing

Strictly sequential: TASK-001 → TASK-002 → TASK-003 → TASK-004. TASK-002 imports `placeFood` and depends
on TASK-001's tests as its only automated check.

## Out of scope

- A "board full" win screen or score bonus. The PRD non-goal says a full board is simply GAME_OVER.
- Any change to `advanceSnake`, movement, speed or scoring. High-score logic changes only in TASK-004.
- Changing `INITIAL_FOOD` in `constants.ts`. It is only the initial state before the first `resetGame`; it is not a fallback.
- Gemini level validation (e.g. rejecting levels whose walls cover the start snake).

## Risks

- **GAME_OVER outside the game loop.** A full board at `resetGame` or after level
  generation would need walls covering almost the whole board. That is unlikely,
  but REQ-003 does not exclude it. The `setStatus(IDLE)` calls in `resetGame` and in
  `handleGenerateLevel`'s `finally` can silently undo the GAME_OVER. No test renders
  `App`, so only review catches this. If you would rather those two paths not end
  the game (e.g. treat an impossible level as a generation error), say so before
  implementation.
- **High score on a full board.** On the eating tick that fills the board,
  `setScore(s => s + 10)` is queued, and then `handleGameOver` compares the *old*
  `score` from the closure. The final food's 10 points are therefore missing from
  the high score. This is the same pre-existing behaviour as any death and is
  listed as out of scope. Flagging it because a full board is the one ending where
  a player would notice.
- **The acceptance seam is the pure function.** "A food placement sets the status
  to GAME_OVER" is tested as `placeFood` returning `status: GAME_OVER`, not by
  watching `App` state. This is the same decision as in plan #1.
- **Performance.** Enumeration scans 400 cells and does a set lookup per cell on
  each placement. That is negligible at 20×20. It would only matter if `GRID_SIZE`
  grew by orders of magnitude.
