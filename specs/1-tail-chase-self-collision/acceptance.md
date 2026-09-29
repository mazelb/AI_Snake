---
title: Let the snake's head enter the cell its tail vacates on the same tick
issue: mazelb/AI_Snake#1
prd: specs/1-tail-chase-self-collision/prd.md
prd_fingerprint: 7307385c41f4c84e
status: frozen
created: 2026-09-29
---

# Acceptance — Let the snake's head enter the cell its tail vacates on the same tick

These cases are derived from the PRD, before implementation exists, and are frozen
once written. They describe what the requirement demands, never what the code does.

Coordinates are `(x, y)` with `y` increasing downward; the first listed segment is
the head, the last is the tail. All positions are inside the grid bounds and no
level walls are present unless stated, so boundary and wall collisions cannot
affect the outcome.

## AC-001 [REQ-001] Length-4 snake in a 2x2 loop enters its vacating tail cell

- Type: automated
- Given: status PLAYING; snake `[(5,5), (6,5), (6,6), (5,6)]` (length 4); direction DOWN; food at `(10,10)`; no walls
- When: one game tick runs
- Then: status is PLAYING; snake is exactly `[(5,6), (5,5), (6,5), (6,6)]` — length 4, head at `(5,6)`
- Fails if: the self-collision check compares the new head against the full current snake including the last segment before the tail is removed, so the tick reports GAME_OVER (the bug in issue #1)

## AC-002 [REQ-001] Tail is still removed when the head takes its cell

- Type: automated
- Given: the same starting state as AC-001
- When: one game tick runs
- Then: the resulting snake has length 4 (not 5), `(6,6)` is its last segment, and `(5,6)` appears exactly once in it
- Fails if: the fix avoids GAME_OVER by skipping the tail pop (or treating the move as eating), so the snake grows to length 5 or holds `(5,6)` twice

## AC-003 [REQ-001] Longer snake enters its vacating tail cell

- Type: automated
- Given: status PLAYING; snake `[(5,5), (4,5), (3,5), (3,6), (4,6), (5,6)]` (length 6); direction DOWN; food at `(10,10)`; no walls
- When: one game tick runs
- Then: status is PLAYING; snake is exactly `[(5,6), (5,5), (4,5), (3,5), (3,6), (4,6)]` — length 6, head at `(5,6)`
- Fails if: the exemption is hard-coded to length 4 or to a fixed segment index instead of the last segment, so a longer snake still dies on its vacating tail

## AC-004 [REQ-002] Head into a middle segment ends the game

- Type: automated
- Given: status PLAYING; snake `[(5,5), (6,5), (6,6), (5,6), (4,6)]` (length 5); direction DOWN; food at `(10,10)`; no walls
- When: one game tick runs, moving the head to `(5,6)` — segment index 3 (length−2), not the tail
- Then: status is GAME_OVER after that single tick (not PLAYING)
- Fails if: the fix exempts more than the last segment (e.g. drops the last two segments, or skips self-collision entirely on non-eating ticks), so the head passes through the second-to-last segment

## AC-005 [REQ-002] Head into the segment right behind it ends the game

- Type: automated
- Given: status PLAYING; snake `[(5,5), (6,5), (6,6), (5,6)]` (length 4); direction RIGHT; food at `(10,10)`; no walls
- When: one game tick runs, moving the head to `(6,5)` — segment index 1
- Then: status is GAME_OVER after that single tick (not PLAYING)
- Fails if: the self-collision check starts at the wrong index (e.g. slices off the first body segment along with the tail), so a head moving into index 1 survives

## AC-006 [REQ-002] Head into an early body segment of a long snake ends the game

- Type: automated
- Given: status PLAYING; snake `[(5,5), (5,4), (6,4), (6,5), (6,6), (5,6), (4,6)]` (length 7); direction RIGHT; food at `(10,10)`; no walls
- When: one game tick runs, moving the head to `(6,5)` — segment index 3
- Then: status is GAME_OVER after that single tick (not PLAYING)
- Fails if: the self-collision check only inspects a fixed window of segments near the head or tail, so a hit on a segment in the middle of a long body is missed

## Not covered

- REQ-003 (tail cell is fatal on an eating tick) is withdrawn by the owner on
  2026-09-29: food never spawns on a snake cell, so the case cannot occur in play.
  No case is written for it, and none of the cases above constrain behaviour when
  the food cell equals the tail cell.
