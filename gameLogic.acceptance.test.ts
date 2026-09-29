import { describe, expect, test } from 'vitest';
import { advanceSnake } from './gameLogic';
import { Direction, GameStatus, Point } from './types';

// Acceptance tests for issue #1 (specs/1-tail-chase-self-collision/acceptance.md).
// One call to advanceSnake is one game tick (plan.md, TASK-001 seam).
// Coordinates are (x, y) with y increasing downward; snake[0] is the head.

const p = (x: number, y: number): Point => ({ x, y });
const FOOD_ELSEWHERE = p(10, 10);
const NO_WALLS: Point[] = [];

describe('issue #1: tail-chase self-collision', () => {
  test('AC-001 length-4 snake in a 2x2 loop enters its vacating tail cell', () => {
    const snake = [p(5, 5), p(6, 5), p(6, 6), p(5, 6)];

    const result = advanceSnake(snake, Direction.DOWN, FOOD_ELSEWHERE, NO_WALLS);

    expect(result.status).toBe(GameStatus.PLAYING);
    expect(result.snake).toEqual([p(5, 6), p(5, 5), p(6, 5), p(6, 6)]);
    expect(result.snake).toHaveLength(4);
    expect(result.snake[0]).toEqual(p(5, 6));
  });

  test('AC-002 tail is still removed when the head takes its cell', () => {
    const snake = [p(5, 5), p(6, 5), p(6, 6), p(5, 6)];

    const result = advanceSnake(snake, Direction.DOWN, FOOD_ELSEWHERE, NO_WALLS);

    expect(result.snake).toHaveLength(4);
    expect(result.snake[result.snake.length - 1]).toEqual(p(6, 6));
    const occurrences = result.snake.filter((s) => s.x === 5 && s.y === 6).length;
    expect(occurrences).toBe(1);
  });

  test('AC-003 longer snake enters its vacating tail cell', () => {
    const snake = [p(5, 5), p(4, 5), p(3, 5), p(3, 6), p(4, 6), p(5, 6)];

    const result = advanceSnake(snake, Direction.DOWN, FOOD_ELSEWHERE, NO_WALLS);

    expect(result.status).toBe(GameStatus.PLAYING);
    expect(result.snake).toEqual([p(5, 6), p(5, 5), p(4, 5), p(3, 5), p(3, 6), p(4, 6)]);
    expect(result.snake).toHaveLength(6);
    expect(result.snake[0]).toEqual(p(5, 6));
  });

  test('AC-004 head into a middle segment (length-2) ends the game', () => {
    const snake = [p(5, 5), p(6, 5), p(6, 6), p(5, 6), p(4, 6)];

    const result = advanceSnake(snake, Direction.DOWN, FOOD_ELSEWHERE, NO_WALLS);

    expect(result.status).toBe(GameStatus.GAME_OVER);
  });

  test('AC-005 head into the segment right behind it ends the game', () => {
    const snake = [p(5, 5), p(6, 5), p(6, 6), p(5, 6)];

    const result = advanceSnake(snake, Direction.RIGHT, FOOD_ELSEWHERE, NO_WALLS);

    expect(result.status).toBe(GameStatus.GAME_OVER);
  });

  test('AC-006 head into an early body segment of a long snake ends the game', () => {
    const snake = [p(5, 5), p(5, 4), p(6, 4), p(6, 5), p(6, 6), p(5, 6), p(4, 6)];

    const result = advanceSnake(snake, Direction.RIGHT, FOOD_ELSEWHERE, NO_WALLS);

    expect(result.status).toBe(GameStatus.GAME_OVER);
  });
});
