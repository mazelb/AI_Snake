export interface Point {
  x: number;
  y: number;
}

export enum Direction {
  UP = 'UP',
  DOWN = 'DOWN',
  LEFT = 'LEFT',
  RIGHT = 'RIGHT',
}

export enum GameStatus {
  IDLE = 'IDLE',
  PLAYING = 'PLAYING',
  PAUSED = 'PAUSED',
  GAME_OVER = 'GAME_OVER',
  GENERATING_LEVEL = 'GENERATING_LEVEL',
}

export interface LevelConfig {
  name: string;
  walls: Point[];
  description?: string;
}

export interface GameState {
  snake: Point[];
  food: Point;
  direction: Direction;
  nextDirection: Direction; // To prevent rapid double turns
  status: GameStatus;
  score: number;
  highScore: number;
  level: LevelConfig;
}