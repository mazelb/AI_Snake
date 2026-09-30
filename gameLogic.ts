import { GameStatus, Direction, Point } from './types';
import { GRID_SIZE, DIRECTIONS } from './constants';

export interface TickOutcome {
  status: GameStatus.PLAYING | GameStatus.GAME_OVER;
  snake: Point[];
  ate: boolean;
}

export type FoodPlacement =
  | { status: GameStatus.PLAYING; food: Point }
  | { status: GameStatus.GAME_OVER; food: null };

const samePoint = (a: Point, b: Point) => a.x === b.x && a.y === b.y;

// Pick food from the cells free of snake and walls, scanned row by row, so
// every value of random() in [0, 1) lands on a free cell. A full board is
// GAME_OVER.
export function placeFood(
  snake: Point[],
  walls: Point[],
  random: () => number = Math.random,
): FoodPlacement {
  const key = (p: Point) => `${p.x},${p.y}`;
  const occupied = new Set([...snake, ...walls].map(key));

  const free: Point[] = [];
  for (let y = 0; y < GRID_SIZE; y++) {
    for (let x = 0; x < GRID_SIZE; x++) {
      if (!occupied.has(key({ x, y }))) free.push({ x, y });
    }
  }

  if (free.length === 0) {
    return { status: GameStatus.GAME_OVER, food: null };
  }
  return { status: GameStatus.PLAYING, food: free[Math.floor(random() * free.length)] };
}

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
