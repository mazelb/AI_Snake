import { describe, it, expect } from 'vitest';
import { advanceSnake, placeFood, placeFoodForNewLevel } from './gameLogic';
import { Direction, GameStatus, Point } from './types';
import { GRID_SIZE } from './constants';

const farFood: Point = { x: 0, y: 19 };

describe('advanceSnake', () => {
  it('moves one cell and drops the tail when not eating', () => {
    const snake = [{ x: 10, y: 10 }, { x: 10, y: 11 }, { x: 10, y: 12 }];
    const result = advanceSnake(snake, Direction.UP, farFood, []);
    expect(result).toEqual({
      status: GameStatus.PLAYING,
      ate: false,
      snake: [{ x: 10, y: 9 }, { x: 10, y: 10 }, { x: 10, y: 11 }],
    });
  });

  it('grows when the head lands on food', () => {
    const snake = [{ x: 10, y: 10 }, { x: 10, y: 11 }, { x: 10, y: 12 }];
    const result = advanceSnake(snake, Direction.UP, { x: 10, y: 9 }, []);
    expect(result.status).toBe(GameStatus.PLAYING);
    expect(result.ate).toBe(true);
    expect(result.snake).toEqual([{ x: 10, y: 9 }, ...snake]);
  });

  it('ends the game at the grid boundary', () => {
    const snake = [{ x: 0, y: 3 }, { x: 1, y: 3 }];
    const result = advanceSnake(snake, Direction.LEFT, farFood, []);
    expect(result.status).toBe(GameStatus.GAME_OVER);
    expect(result.snake).toBe(snake);
  });

  it('ends the game on a level wall', () => {
    const snake = [{ x: 4, y: 4 }, { x: 4, y: 5 }];
    const result = advanceSnake(snake, Direction.UP, farFood, [{ x: 4, y: 3 }]);
    expect(result.status).toBe(GameStatus.GAME_OVER);
    expect(result.snake).toBe(snake);
  });

  describe('REQ-001: the head may enter the cell the tail vacates', () => {
    // A 2x2 loop: head (5,5) moving DOWN lands on the tail at (5,6).
    const loop = [{ x: 5, y: 5 }, { x: 6, y: 5 }, { x: 6, y: 6 }, { x: 5, y: 6 }];

    it('is not fatal on a tick without food', () => {
      const result = advanceSnake(loop, Direction.DOWN, farFood, []);
      expect(result.status).toBe(GameStatus.PLAYING);
      expect(result.ate).toBe(false);
      expect(result.snake).toHaveLength(4);
      expect(result.snake[0]).toEqual({ x: 5, y: 6 });
      expect(result.snake).toEqual([{ x: 5, y: 6 }, { x: 5, y: 5 }, { x: 6, y: 5 }, { x: 6, y: 6 }]);
    });

    it('stays fatal on an eating tick, where the tail does not move', () => {
      const result = advanceSnake(loop, Direction.DOWN, { x: 5, y: 6 }, []);
      expect(result.status).toBe(GameStatus.GAME_OVER);
      expect(result.snake).toBe(loop);
    });
  });

  describe('REQ-002: body segments other than the tail are fatal', () => {
    // A snake whose head, moving UP, lands on segment i. The other segments
    // sit on distinct cells along the top row, clear of the head's path.
    const snakeHitting = (i: number, length: number): Point[] => {
      const body: Point[] = [];
      for (let k = 1; k < length; k++) {
        body.push(k === i ? { x: 10, y: 10 } : { x: k, y: 0 });
      }
      return [{ x: 10, y: 11 }, ...body];
    };

    it.each([
      [1, 4], [2, 4],
      [1, 6], [2, 6], [3, 6], [4, 6],
    ])('segment %i of a length-%i snake', (i, length) => {
      const snake = snakeHitting(i, length);
      const result = advanceSnake(snake, Direction.UP, farFood, []);
      expect(result.status).toBe(GameStatus.GAME_OVER);
      expect(result.snake).toBe(snake);
    });
  });
});

describe('placeFood', () => {
  // Every cell of the grid except `free`, split between a snake and walls.
  const fillAllBut = (free: Point[]): { snake: Point[]; walls: Point[] } => {
    const cells: Point[] = [];
    for (let y = 0; y < GRID_SIZE; y++) {
      for (let x = 0; x < GRID_SIZE; x++) {
        if (!free.some(f => f.x === x && f.y === y)) cells.push({ x, y });
      }
    }
    return { snake: cells.slice(0, 50), walls: cells.slice(50) };
  };

  const stubs = [() => 0, () => 0.5, () => 0.999999];

  describe('REQ-001: food lands on the only free cell', () => {
    it.each([
      [{ x: 0, y: 0 }],
      [{ x: 13, y: 7 }],
      [{ x: 19, y: 19 }],
    ])('free cell %o', (freeCell) => {
      const { snake, walls } = fillAllBut([freeCell]);
      for (const random of stubs) {
        expect(placeFood(snake, walls, random)).toEqual({
          status: GameStatus.PLAYING,
          food: freeCell,
        });
      }
    });

    it('never picks a snake or wall cell on a partly filled board', () => {
      const { snake, walls } = fillAllBut([{ x: 2, y: 3 }, { x: 17, y: 11 }]);
      for (const random of stubs) {
        const { food } = placeFood(snake, walls, random);
        expect([{ x: 2, y: 3 }, { x: 17, y: 11 }]).toContainEqual(food);
      }
    });
  });

  describe('REQ-003: a full board ends the game', () => {
    it('returns GAME_OVER and no food', () => {
      const { snake, walls } = fillAllBut([]);
      expect(snake.length + walls.length).toBe(GRID_SIZE * GRID_SIZE);
      for (const random of stubs) {
        expect(placeFood(snake, walls, random)).toEqual({
          status: GameStatus.GAME_OVER,
          food: null,
        });
      }
    });
  });

  it('indexes free cells row by row from (0,0)', () => {
    expect(placeFood([], [], () => 0).food).toEqual({ x: 0, y: 0 });
    expect(placeFood([], [], () => 0.999999).food).toEqual({ x: 19, y: 19 });
  });
});

describe('placeFoodForNewLevel', () => {
  const startSnake = [{ x: 10, y: 10 }, { x: 10, y: 11 }, { x: 10, y: 12 }];

  // Walls on every cell except the start snake and `free`.
  const wallsAllBut = (free: Point[]): Point[] => {
    const walls: Point[] = [];
    for (let y = 0; y < GRID_SIZE; y++) {
      for (let x = 0; x < GRID_SIZE; x++) {
        const p = { x, y };
        const open = [...startSnake, ...free].some(f => f.x === x && f.y === y);
        if (!open) walls.push(p);
      }
    }
    return walls;
  };

  describe('REQ-005: food is placed once, against the new level walls', () => {
    it('lands on a cell the new level leaves free, not one the old level did', () => {
      // The old level walled off (3,4); the new level frees only that cell.
      const newWalls = wallsAllBut([{ x: 3, y: 4 }]);
      for (const random of [() => 0, () => 0.5, () => 0.999999]) {
        expect(placeFoodForNewLevel(startSnake, newWalls, random)).toEqual({
          status: GameStatus.PLAYING,
          food: { x: 3, y: 4 },
        });
      }
    });

    it('never lands on a new wall or the start snake', () => {
      const newWalls = wallsAllBut([{ x: 0, y: 0 }, { x: 19, y: 0 }, { x: 5, y: 17 }]);
      for (const random of [() => 0, () => 0.3, () => 0.7, () => 0.999999]) {
        const { food } = placeFoodForNewLevel(startSnake, newWalls, random);
        expect(newWalls).not.toContainEqual(food);
        expect(startSnake).not.toContainEqual(food);
      }
    });

    it('draws from the random source exactly once', () => {
      let calls = 0;
      placeFoodForNewLevel(startSnake, [], () => { calls++; return 0.5; });
      expect(calls).toBe(1);
    });

    it('ends the game when the new level leaves no free cell', () => {
      expect(placeFoodForNewLevel(startSnake, wallsAllBut([]), () => 0)).toEqual({
        status: GameStatus.GAME_OVER,
        food: null,
      });
    });
  });
});
