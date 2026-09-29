---
title: Let the snake's head enter the cell its tail vacates on the same tick
issue: mazelb/AI_Snake#1
prd: specs/1-tail-chase-self-collision/prd.md
owner: mazelb
status: approved
created: 2026-09-29
---

# Plan — Let the snake's head enter the cell its tail vacates on the same tick

## Approach

All movement and collision logic currently lives inside the `gameLoop` callback in
`App.tsx`, tangled with React state setters, so nothing can be tested without
rendering. The first step moves the per-tick rules into a new pure module,
`gameLogic.ts` at the repo root (next to `types.ts` and `constants.ts`). It exports
`advanceSnake(snake, direction, food, walls)`, which returns
`{ status: GameStatus.PLAYING | GameStatus.GAME_OVER, snake: Point[], ate: boolean }`.
`gameLoop` keeps the side effects: `setDirection`, `handleGameOver`,
score/speed updates, `getRandomPoint` food respawn and `setSnake`. It just acts on
the returned outcome. The extraction preserves current behaviour, so the tests
written in that step pin REQ-002 before anything changes. The second step changes
one rule inside `advanceSnake`: settle whether the head lands on food *before* the
self-collision check, and when it does not, leave the last segment out of the
hazard set. Boundary and level-wall checks move over verbatim and keep their order.

## Skipped steps

None.

## Tasks

### TASK-001 Extract the tick rules from gameLoop into a pure advanceSnake

- Satisfies: REQ-002
- Touches: gameLogic.ts (new), gameLogic.test.ts (new), App.tsx
- Seams: `advanceSnake(snake, direction, food, walls)` exported from `gameLogic.ts` — the input/output boundary of one game tick, with no React
- Done when: `npx vitest run` passes with `gameLogic.test.ts` tests showing that a head moving onto any segment at index 1..length−2 yields `status: GAME_OVER` and an unchanged snake; `App.tsx` `gameLoop` calls `advanceSnake` and no longer does its own bounds/wall/self checks; `npx tsc --noEmit` passes

Move the head computation (`DIRECTIONS[direction]`), the `GRID_SIZE` bounds check,
the `level.walls` check, the self-overlap check, and the grow-or-pop step out of
`gameLoop` into `advanceSnake`. The behaviour stays exactly as it is today, tail
included. Remove the stale "keep it simple" comments along with the moved code.
`gameLoop` then branches on `status` and `ate`. Food respawn stays in `App.tsx`
because it uses `Math.random` through `getRandomPoint`.

### TASK-002 Exclude the vacating tail from the self-collision hazard set

- Satisfies: REQ-001
- Touches: gameLogic.ts, gameLogic.test.ts
- Seams: `advanceSnake` in `gameLogic.ts` (same seam as TASK-001)
- Done when: a new `gameLogic.test.ts` case passes: a length-4 snake whose next head equals its last segment, with food elsewhere, returns `status: PLAYING`, `ate: false`, length 4, and `snake[0]` at the old tail cell. The TASK-001 REQ-002 tests still pass

Inside `advanceSnake`, compute `ate` before the self-collision check. Then check
the new head against `snake.slice(0, -1)` when not eating, and against the whole
snake when eating. The eating branch keeps the full check even though REQ-003 is
withdrawn: keeping it costs nothing, and dropping it would be a behaviour change
nobody asked for.

## Sequencing

Strictly sequential: TASK-001 → TASK-002. TASK-002 edits the function that
TASK-001 creates, and relies on TASK-001's REQ-002 tests as its regression net.

## Out of scope

- REQ-003: withdrawn in the PRD, so no task and no test. TASK-002 still keeps the whole snake as a hazard on an eating tick, which leaves today's behaviour unchanged.
- A `test` script in `package.json`. `flow.json` already runs `npx vitest run` directly.
- A separate `vitest.config.ts`. Vitest picks up `vite.config.ts`, and the new module is pure, so it needs no DOM environment.
- Moving `getRandomPoint`, the keyboard handling or `handleGameOver` out of `App.tsx`.
- The food-spawn `(0,0)` fallback and the missing entry script in `index.html` (PRD non-goals).
- Any change to boundary, level-wall, speed, score or high-score behaviour.

## Risks

- **Stale-closure behaviour in `gameLoop`.** `handleGameOver` reads `score` from
  the closure, and `gameLoop`'s dependency list will change once it calls
  `advanceSnake`. The extraction has to keep the dependency array accurate, or the
  interval can run against stale `snake`/`food`. No test covers `App.tsx` wiring,
  so this relies on review plus `tsc`.
- **The acceptance seam is the pure function, not the rendered game.** REQ-001/002
  acceptance says "one game tick sets the status". This plan treats the
  `advanceSnake` return value as that tick. If you expect acceptance tests to drive
  the real `App` component, that needs jsdom and a testing library as new dev
  dependencies, which is a different plan.
- **Vitest loading `vite.config.ts`.** The config uses `__dirname` and `loadEnv` in
  an ESM package. Vite's config bundler normally handles this, but it has not run
  under vitest in this repo yet (there are no tests so far). If it fails, the fix
  is a minimal `vitest.config.ts`, which I would raise with you rather than add
  silently.
