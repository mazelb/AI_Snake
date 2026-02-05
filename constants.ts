import { Point, LevelConfig } from './types';

export const GRID_SIZE = 20; // 20x20 grid
export const INITIAL_SPEED = 150; // ms per tick
export const MIN_SPEED = 50;
export const SPEED_DECREMENT = 2; // Decrease ms per food eaten

export const INITIAL_SNAKE: Point[] = [
  { x: 10, y: 10 },
  { x: 10, y: 11 },
  { x: 10, y: 12 },
];

export const INITIAL_FOOD: Point = { x: 5, y: 5 };

export const DEFAULT_LEVEL: LevelConfig = {
  name: "Classic Open",
  walls: [],
  description: "An open field with no obstacles.",
};

export const DIRECTIONS = {
  UP: { x: 0, y: -1 },
  DOWN: { x: 0, y: 1 },
  LEFT: { x: -1, y: 0 },
  RIGHT: { x: 1, y: 0 },
};