import { describe, expect, test } from 'vitest';
import { placeFood } from './gameLogic';
import { GRID_SIZE } from './constants';
import { GameStatus, Point } from './types';

// Acceptance tests for issue #4 (specs/4-food-never-on-snake-or-wall/acceptance.md).
// Seam: placeFood(snake, walls, random) in gameLogic.ts (plan.md, TASK-001).
// It returns { status: PLAYING, food } or { status: GAME_OVER, food: null }.
//
// A "hostile random source" is a constant stub. With the old
// getRandomPoint-style draw (x = floor(r * GRID_SIZE), y = floor(r * GRID_SIZE))
// a constant r always lands on (floor(r * GRID_SIZE), floor(r * GRID_SIZE)),
// which each test makes an occupied cell. Several constants are tried so a
// result cannot come from one lucky value.

const p = (x: number, y: number): Point => ({ x, y });
const key = (c: Point) => `${c.x},${c.y}`;
const LAST = GRID_SIZE - 1;

const allCells = (): Point[] => {
  const cells: Point[] = [];
  for (let y = 0; y < GRID_SIZE; y++) {
    for (let x = 0; x < GRID_SIZE; x++) cells.push(p(x, y));
  }
  return cells;
};

// Walls = every cell not in the snake and not in `free`.
const wallsLeaving = (snake: Point[], free: Point[]): Point[] => {
  const taken = new Set([...snake, ...free].map(key));
  return allCells().filter((c) => !taken.has(key(c)));
};

// Constant stub whose old-style draw lands on the diagonal cell (i, i).
const alwaysDiagonal = (i: number) => () => (i + 0.5) / GRID_SIZE;

const HOSTILE_STUBS: Array<[string, () => number]> = [
  ['() => 0', () => 0],
  ['() => 0.5', () => 0.5],
  ['() => 0.999999', () => 0.999999],
];

const expectNotOccupied = (food: Point | null | undefined, occupied: Point[]) => {
  if (food == null) return;
  const set = new Set(occupied.map(key));
  expect(set.has(key(food))).toBe(false);
};

describe('issue #4: food always placed on a free cell', () => {
  test('AC-001 single free corner cell is found despite a hostile random source', () => {
    const free = p(LAST, LAST);
    const snake = [p(2, 0), p(1, 0), p(0, 0)]; // (0,0) is a snake cell
    const walls = wallsLeaving(snake, [free]);

    // Sanity: the setup leaves exactly one free cell, and (0,0) is occupied.
    expect(snake.length + walls.length).toBe(GRID_SIZE * GRID_SIZE - 1);
    expect(snake.some((s) => s.x === 0 && s.y === 0)).toBe(true);

    for (const random of [() => 0, alwaysDiagonal(0)]) {
      const result = placeFood(snake, walls, random);
      expect(result.status).toBe(GameStatus.PLAYING);
      expect(result.food).toEqual({ x: GRID_SIZE - 1, y: GRID_SIZE - 1 });
      expect(result.food).not.toEqual({ x: 0, y: 0 });
    }
  });

  test('AC-002 a different, interior single free cell is also found', () => {
    const free = p(7, 3);
    const snake = [p(2, 0), p(1, 0), p(0, 0)];
    const walls = wallsLeaving(snake, [free]);
    expect(snake.length + walls.length).toBe(GRID_SIZE * GRID_SIZE - 1);

    for (const [, random] of HOSTILE_STUBS) {
      const result = placeFood(snake, walls, random);
      expect(result.status).toBe(GameStatus.PLAYING);
      expect(result.food).toEqual({ x: 7, y: 3 });
    }
    // Also with stubs that pin to other occupied diagonal cells (walls).
    for (const i of [0, 5, 10, LAST]) {
      const result = placeFood(snake, walls, alwaysDiagonal(i));
      expect(result.food).toEqual({ x: 7, y: 3 });
    }
  });

  test('AC-003 wall cells are treated as occupied', () => {
    const free = p(13, 17);
    const snake = [p(3, 1), p(2, 1), p(1, 1)]; // short snake, away from the diagonal (10,10)
    const walls = wallsLeaving(snake, [free]);

    // The hostile draw (10,10) is a wall cell, not a snake cell.
    expect(walls.some((w) => w.x === 10 && w.y === 10)).toBe(true);
    expect(snake.some((s) => s.x === 10 && s.y === 10)).toBe(false);

    for (const random of [alwaysDiagonal(10), alwaysDiagonal(0), alwaysDiagonal(LAST)]) {
      const result = placeFood(snake, walls, random);
      expect(result.status).toBe(GameStatus.PLAYING);
      expect(result.food).toEqual(free);
      expectNotOccupied(result.food, walls);
    }
  });

  test('AC-004 snake body cells are treated as occupied', () => {
    // Long snake along row y = 10, head at (LAST, 10), body covering (0..LAST-1, 10),
    // then continuing down along row y = 11 so the snake is long.
    const row10 = Array.from({ length: GRID_SIZE }, (_, i) => p(LAST - i, 10)); // head (LAST,10) ... (0,10)
    const row11 = Array.from({ length: GRID_SIZE }, (_, i) => p(i, 11)); // (0,11) ... (LAST,11)
    const snake = [...row10, ...row11];
    const free = p(4, 15);
    const walls = wallsLeaving(snake, [free]);

    // The hostile draw (10,10) is a snake body segment, not the head, and not a wall.
    const bodyIdx = snake.findIndex((s) => s.x === 10 && s.y === 10);
    expect(bodyIdx).toBeGreaterThan(0);
    expect(walls.some((w) => w.x === 10 && w.y === 10)).toBe(false);

    const result = placeFood(snake, walls, alwaysDiagonal(10));
    expect(result.status).toBe(GameStatus.PLAYING);
    expect(result.food).toEqual(free);
    expectNotOccupied(result.food, snake);

    for (const [, random] of HOSTILE_STUBS) {
      const r = placeFood(snake, walls, random);
      expect(r.food).toEqual(free);
      expectNotOccupied(r.food, snake);
    }
  });

  test('AC-006 a full board ends the game', () => {
    const snake = [p(2, 0), p(1, 0), p(0, 0)]; // includes (0,0)
    const walls = wallsLeaving(snake, []);
    expect(snake.length + walls.length).toBe(GRID_SIZE * GRID_SIZE);

    for (const [, random] of HOSTILE_STUBS) {
      const result = placeFood(snake, walls, random);
      expect(result.status).toBe(GameStatus.GAME_OVER);
      expect(result.status).not.toBe(GameStatus.PLAYING);
      expect(result.food).not.toEqual({ x: 0, y: 0 });
      expectNotOccupied(result.food, [...snake, ...walls]);
    }
  });

  test('AC-007 exactly one free cell does not end the game', () => {
    const free = p(11, 6);
    const snake = [p(2, 0), p(1, 0), p(0, 0)];
    const walls = wallsLeaving(snake, [free]);
    expect(snake.length + walls.length).toBe(GRID_SIZE * GRID_SIZE - 1);

    for (const [, random] of HOSTILE_STUBS) {
      const result = placeFood(snake, walls, random);
      expect(result.status).not.toBe(GameStatus.GAME_OVER);
      expect(result.food).toEqual(free);
    }
  });
});
