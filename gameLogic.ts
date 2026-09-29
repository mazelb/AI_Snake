import { GameStatus, Direction, Point } from './types';
import { GRID_SIZE, DIRECTIONS } from './constants';

export interface TickOutcome {
  status: GameStatus.PLAYING | GameStatus.GAME_OVER;
  snake: Point[];
  ate: boolean;
}

const samePoint = (a: Point, b: Point) => a.x === b.x && a.y === b.y;

// One game tick: move the head, check collisions, then grow or drop the tail.
// On GAME_OVER the input snake is returned unchanged.
export function advanceSnake(
  snake: Point[],
  direction: Direction,
  food: Point,
  walls: Point[],
): TickOutcome {
  const move = DIRECTIONS[direction];
  const head = snake[0];

  const newHead = {
    x: head.x + move.x,
    y: head.y + move.y,
  };

  const gameOver: TickOutcome = { status: GameStatus.GAME_OVER, snake, ate: false };

  // Check Wall Collisions (Boundaries)
  if (
    newHead.x < 0 ||
    newHead.x >= GRID_SIZE ||
    newHead.y < 0 ||
    newHead.y >= GRID_SIZE
  ) {
    return gameOver;
  }

  // Check Wall Collisions (Level Walls)
  if (walls.some(w => samePoint(w, newHead))) {
    return gameOver;
  }

  // Check Self Collision. The tail vacates its cell this tick unless we eat,
  // so it is only a hazard on an eating tick.
  const ate = samePoint(newHead, food);
  const hazards = ate ? snake : snake.slice(0, -1);
  if (hazards.some(s => samePoint(s, newHead))) {
    return gameOver;
  }

  const newSnake = [newHead, ...snake];

  if (!ate) {
    // Remove tail
    newSnake.pop();
  }

  return { status: GameStatus.PLAYING, snake: newSnake, ate };
}
