---
title: Always place food on a free cell
issue: mazelb/AI_Snake#4
prd: specs/4-food-never-on-snake-or-wall/prd.md
prd_fingerprint: d67fa1b303cdb26e
status: frozen
created: 2026-09-30
---

# Acceptance — Always place food on a free cell

These cases are derived from the PRD, before implementation exists, and are frozen
once written. They describe what the requirement demands, never what the code does.

"Free cell" means a cell on the `GRID_SIZE` × `GRID_SIZE` grid that is neither a
snake segment nor a level wall. "Hostile random source" means a random source whose
every draw maps to an occupied cell (for example, one that always returns 0 when
(0,0) is occupied).

## AC-001 [REQ-001] Single free cell found despite a hostile random source

- Type: automated
- Given: a snake and walls that together occupy every cell except (GRID_SIZE-1, GRID_SIZE-1), with (0,0) occupied by the snake, and a hostile random source that always selects (0,0)
- When: the food position is chosen
- Then: the chosen position is exactly { x: GRID_SIZE-1, y: GRID_SIZE-1 }
- Fails if: after the random draws all miss, the placement falls back to { x: 0, y: 0 } or returns the last random draw without checking that it is free

## AC-002 [REQ-001] A different single free cell is also found

- Type: automated
- Given: the same kind of setup as AC-001, but the only free cell is an interior cell (for example { x: 7, y: 3 }), and the hostile random source always selects an occupied cell
- When: the food position is chosen
- Then: the chosen position is exactly that interior free cell ({ x: 7, y: 3 } in the example)
- Fails if: the result is hard-coded or biased to a fixed position (a corner, the first or last scanned cell) rather than the actual free cell

## AC-003 [REQ-001] Wall cells are treated as occupied

- Type: automated
- Given: a short snake, walls that cover every other cell except one free cell, and a random source that always selects a wall cell
- When: the food position is chosen
- Then: the chosen position equals the single free cell and is not any wall cell
- Fails if: only the snake is checked for occupancy, so food is placed on a wall where it can never be eaten

## AC-004 [REQ-001] Snake body cells are treated as occupied

- Type: automated
- Given: no walls except those needed to leave one free cell, a long snake, and a random source that always selects a snake body segment that is not the head
- When: the food position is chosen
- Then: the chosen position equals the single free cell and is not any snake segment
- Fails if: only the snake head (or only the walls) is checked, so food is hidden under the snake's body

## AC-005 [REQ-002] Every food placement in App.tsx uses the free-cell rule with no (0,0) fallback

- Type: manual
- Given: the implemented `App.tsx` and the REQ-001 function
- When: `App.tsx` is inspected at the food set after a tick that ate, in `resetGame`, and in `handleGenerateLevel`, and searched for `x: 0, y: 0`
- Then: all three sites obtain the food position from the REQ-001 function (3 of 3), and the search finds 0 code paths that return or set `{ x: 0, y: 0 }` as a default food position
- Fails if: any one of the three sites still takes its position from the old `getRandomPoint` or its own random logic, or a `{ x: 0, y: 0 }` default remains reachable on any placement path

## AC-006 [REQ-003] A full board ends the game

- Type: automated
- Given: a snake and walls that together cover all GRID_SIZE × GRID_SIZE cells, including (0,0)
- When: a food placement is attempted
- Then: the resulting status is GAME_OVER, and no food position equal to any snake or wall cell is returned (in particular not { x: 0, y: 0 })
- Fails if: the placement returns { x: 0, y: 0 } or another occupied cell as food, loops forever searching for a free cell, or leaves the status as PLAYING

## AC-007 [REQ-003] One free cell does not end the game

- Type: automated
- Given: a snake and walls that leave exactly one free cell
- When: a food placement is attempted
- Then: the status is not GAME_OVER and the food is placed on the one free cell
- Fails if: the full-board check is off by one (e.g. it ends the game when a single cell remains, or counts cells incorrectly)

## AC-008 [REQ-004] Eating on the tick that fills the board counts toward the high score

- Type: automated
- Given: a game with score 90 and a stored high score of 95, a snake whose next move eats the food, and that eating fills the last free cell so the board is full
- When: that tick runs and the game ends because no free cell remains for new food
- Then: the final score is 100 and the saved high score is 100
- Fails if: the high score is compared against the score from before the final tick (90), so the saved high score stays 95, or the game ends before the eaten food's points are added

## AC-009 [REQ-004] A final score below the high score does not replace it

- Type: automated
- Given: a game with score 40 and a stored high score of 95, where the snake eats on a tick that fills the board
- When: that tick runs and the game ends
- Then: the final score is 50 and the saved high score remains 95
- Fails if: the change to count the final tick overwrites the high score with the final score unconditionally, lowering it to 50

## AC-010 [REQ-005] Food after level generation avoids the new level's walls, not the old ones

- Type: automated
- Given: a previous level whose walls cover exactly one cell A (for example { x: 5, y: 5 }), a new level whose walls together with the snake cover every cell except A, and a random source that always selects an occupied cell of the new level
- When: the new level is generated and food is placed
- Then: the food is at exactly cell A, and on none of the new level's wall cells
- Fails if: placement is checked against the previous level's walls (which excludes A and puts the food on one of the new walls), or the food from before generation is kept

## AC-011 [REQ-005] A full new board ends the game instead of keeping old food

- Type: automated
- Given: a game in progress with food at some cell F, and a new level whose walls together with the snake cover every cell on the grid, including F
- When: the new level is generated
- Then: the status is GAME_OVER and no food is left on an occupied cell (in particular not at F)
- Fails if: when no free cell exists the old food at F is left on the board under a new wall and play continues, or placement falls back to { x: 0, y: 0 }

## AC-012 [REQ-005] Level generation places food exactly once

- Type: automated
- Given: a game in progress and a new level that leaves at least one free cell
- When: the new level is generated
- Then: the food placement rule is applied exactly 1 time for that generation, and its result is the food position afterwards
- Fails if: food is placed twice (once against the previous level's walls and again against the new ones, or once in the generate handler and again in a reset it calls), so a placement against stale walls happens or ends the game wrongly

## Not covered

- REQ-002 at runtime: there is no component-rendering test infrastructure (no React testing library in a zero-new-dependency setup), so whether the three `App.tsx` placements actually run through the REQ-001 function while playing is verified by code inspection (AC-005), not by an automated test that eats food, resets, or generates a level in the rendered app.
- REQ-003 wiring in `App.tsx`: AC-006 checks the placement logic yields GAME_OVER; that the React state in `App.tsx` actually switches to the game-over screen on a full board is not exercised by an automated test, for the same missing-infrastructure reason. It is also impractical to reach manually, since it requires filling the whole grid.
- REQ-004 persistence: AC-008 and AC-009 check the high score produced when the game ends; that the value is written to the browser storage the app reads on reload is not exercised end to end, since there is no rendered-app or browser test infrastructure.
- REQ-005 in the rendered app: AC-010 to AC-012 check the level-application logic; that `handleGenerateLevel` in `App.tsx` drives it after a real Gemini call is not tested, because it needs a network call to Gemini and component-rendering infrastructure that does not exist.
