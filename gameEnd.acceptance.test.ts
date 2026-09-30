import { describe, expect, test } from 'vitest';
import { advanceSnake, highScoreAfterTick, placeFood, placeFoodForNewLevel } from './gameLogic';
import { GRID_SIZE, INITIAL_SNAKE } from './constants';
import { Direction, GameStatus, Point } from './types';

// Acceptance tests for issue #4, REQ-004 and REQ-005
// (specs/4-food-never-on-snake-or-wall/acceptance.md, AC-008..AC-012).
//
// Seams (plan.md TASK-003, TASK-004; the plan describes them but does not name
// them, so these names are the contract the implementation must export):
//   placeFoodForNewLevel(startSnake, walls, random) -> FoodPlacement
//     ({ status: PLAYING, food } or { status: GAME_OVER, food: null })
//   highScoreAfterTick(scoreBeforeTick, pointsEarnedOnTick, highScore) -> number
// One call to advanceSnake is one game tick; eating one food is worth 10 points.

const p = (x: number, y: number): Point => ({ x, y });
const key = (c: Point) => `${c.x},${c.y}`;
const FOOD_POINTS = 10;

const allCells = (): Point[] => {
  const cells: Point[] = [];
  for (let y = 0; y < GRID_SIZE; y++) {
    for (let x = 0; x < GRID_SIZE; x++) cells.push(p(x, y));
  }
  return cells;
};

// Walls = every cell not in `keep`.
const wallsLeaving = (keep: Point[]): Point[] => {
  const taken = new Set(keep.map(key));
  return allCells().filter((c) => !taken.has(key(c)));
};

const isOn = (c: Point | null | undefined, cells: Point[]) =>
  c != null && cells.some((o) => o.x === c.x && o.y === c.y);

const HOSTILE_STUBS: Array<() => number> = [() => 0, () => 0.5, () => 0.999999];

// Runs the tick on which the snake eats the last free cell, then the food
// placement that follows it. Returns the tick outcome and the placement.
const runBoardFillingTick = () => {
  const food = p(0, 0);
  const snake = [p(1, 0), p(2, 0), p(3, 0)]; // head (1,0), moving LEFT eats (0,0)
  const walls = wallsLeaving([food, ...snake]);
  expect(snake.length + walls.length).toBe(GRID_SIZE * GRID_SIZE - 1);

  const tick = advanceSnake(snake, Direction.LEFT, food, walls);
  const placement = placeFood(tick.snake, walls, () => 0);
  return { tick, placement };
};

describe('issue #4: high score counts the final tick (REQ-004)', () => {
  test('AC-008 eating on the tick that fills the board counts toward the high score', () => {
    const scoreBefore = 90;
    const storedHighScore = 95;

    const { tick, placement } = runBoardFillingTick();
    expect(tick.ate).toBe(true);
    expect(tick.status).not.toBe(GameStatus.GAME_OVER);
    expect(placement.status).toBe(GameStatus.GAME_OVER);

    const pointsEarned = tick.ate ? FOOD_POINTS : 0;
    const finalScore = scoreBefore + pointsEarned;
    const savedHighScore = highScoreAfterTick(scoreBefore, pointsEarned, storedHighScore);

    expect(finalScore).toBe(100);
    expect(savedHighScore).toBe(100);
    expect(savedHighScore).not.toBe(95);
  });

  test('AC-009 a final score below the high score does not replace it', () => {
    const scoreBefore = 40;
    const storedHighScore = 95;

    const { tick, placement } = runBoardFillingTick();
    expect(tick.ate).toBe(true);
    expect(placement.status).toBe(GameStatus.GAME_OVER);

    const pointsEarned = tick.ate ? FOOD_POINTS : 0;
    const finalScore = scoreBefore + pointsEarned;
    const savedHighScore = highScoreAfterTick(scoreBefore, pointsEarned, storedHighScore);

    expect(finalScore).toBe(50);
    expect(savedHighScore).toBe(95);
    expect(savedHighScore).not.toBe(50);
  });
});

describe('issue #4: a new level places food once, against its own walls (REQ-005)', () => {
  test("AC-010 food after level generation avoids the new level's walls, not the old ones", () => {
    const snake = INITIAL_SNAKE;
    const cellA = p(5, 5);
    const previousWalls = [cellA];
    const newWalls = wallsLeaving([cellA, ...snake]);
    expect(snake.length + newWalls.length).toBe(GRID_SIZE * GRID_SIZE - 1);
    expect(isOn(cellA, newWalls)).toBe(false);
    expect(isOn(cellA, previousWalls)).toBe(true);

    for (const random of HOSTILE_STUBS) {
      const result = placeFoodForNewLevel(snake, newWalls, random);
      expect(result.status).toBe(GameStatus.PLAYING);
      expect(result.food).toEqual({ x: 5, y: 5 });
      expect(isOn(result.food, newWalls)).toBe(false);
      expect(isOn(result.food, snake)).toBe(false);
    }
  });

  test('AC-011 a full new board ends the game instead of keeping old food', () => {
    const snake = INITIAL_SNAKE;
    const oldFood = p(5, 5);
    const newWalls = wallsLeaving(snake);
    expect(snake.length + newWalls.length).toBe(GRID_SIZE * GRID_SIZE);
    expect(isOn(oldFood, newWalls)).toBe(true);

    for (const random of HOSTILE_STUBS) {
      const result = placeFoodForNewLevel(snake, newWalls, random);
      expect(result.status).toBe(GameStatus.GAME_OVER);
      expect(result.food).not.toEqual(oldFood);
      expect(result.food).not.toEqual({ x: 0, y: 0 });
      expect(isOn(result.food, [...snake, ...newWalls])).toBe(false);
    }
  });

  test('AC-012 level generation places food exactly once', () => {
    const snake = INITIAL_SNAKE;
    // A new level that leaves many cells free: a wall along row 0 and column 0.
    const newWalls = allCells().filter((c) => c.x === 0 || c.y === 0);

    // Each placement draws once from the random source to pick among free cells,
    // so the number of draws is the number of placements.
    let draws = 0;
    const countingRandom = () => {
      draws++;
      return 0.37;
    };
    const result = placeFoodForNewLevel(snake, newWalls, countingRandom);

    expect(draws).toBe(1);
    expect(result.status).toBe(GameStatus.PLAYING);
    // Its result is the food position afterwards: the same as one placement
    // against the new level's walls with the same draw.
    expect(result.food).toEqual(placeFood(snake, newWalls, () => 0.37).food);
    expect(isOn(result.food, newWalls)).toBe(false);
    expect(isOn(result.food, snake)).toBe(false);
  });
});
