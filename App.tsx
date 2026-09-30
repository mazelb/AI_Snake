import React, { useState, useEffect, useCallback, useRef } from 'react';
import Grid from './components/Grid.tsx';
import Controls from './components/Controls.tsx';
import { GameStatus, Direction, Point, LevelConfig } from './types';
import { GRID_SIZE, INITIAL_SPEED, INITIAL_SNAKE, INITIAL_FOOD, SPEED_DECREMENT, MIN_SPEED, DEFAULT_LEVEL } from './constants';
import { generateLevel } from './services/geminiService';
import { advanceSnake, placeFood, placeFoodForNewLevel } from './gameLogic';

// Custom hook for interval handling
function useInterval(callback: () => void, delay: number | null) {
  const savedCallback = useRef(callback);

  useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);

  useEffect(() => {
    if (delay !== null) {
      const id = setInterval(() => savedCallback.current(), delay);
      return () => clearInterval(id);
    }
  }, [delay]);
}

const App: React.FC = () => {
  // Game State
  const [snake, setSnake] = useState<Point[]>(INITIAL_SNAKE);
  const [food, setFood] = useState<Point>(INITIAL_FOOD);
  const [direction, setDirection] = useState<Direction>(Direction.UP);
  const [nextDirection, setNextDirection] = useState<Direction>(Direction.UP);
  const [status, setStatus] = useState<GameStatus>(GameStatus.IDLE);
  const [score, setScore] = useState<number>(0);
  const [highScore, setHighScore] = useState<number>(0);
  const [speed, setSpeed] = useState<number>(INITIAL_SPEED);
  
  // Level State
  const [level, setLevel] = useState<LevelConfig>(DEFAULT_LEVEL);
  const [loadingMessage, setLoadingMessage] = useState<string>('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Keyboard controls
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (status !== GameStatus.PLAYING) return;

      switch (e.key) {
        case 'ArrowUp':
        case 'w':
        case 'W':
          if (direction !== Direction.DOWN) setNextDirection(Direction.UP);
          break;
        case 'ArrowDown':
        case 's':
        case 'S':
          if (direction !== Direction.UP) setNextDirection(Direction.DOWN);
          break;
        case 'ArrowLeft':
        case 'a':
        case 'A':
          if (direction !== Direction.RIGHT) setNextDirection(Direction.LEFT);
          break;
        case 'ArrowRight':
        case 'd':
        case 'D':
          if (direction !== Direction.LEFT) setNextDirection(Direction.RIGHT);
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [direction, status]);

  // Game Loop
  const gameLoop = useCallback(() => {
    if (status !== GameStatus.PLAYING) return;

    setDirection(nextDirection);
    const outcome = advanceSnake(snake, nextDirection, food, level.walls);

    if (outcome.status === GameStatus.GAME_OVER) {
      handleGameOver();
      return;
    }

    if (outcome.ate) {
      setScore(s => s + 10);
      setSpeed(s => Math.max(MIN_SPEED, s - SPEED_DECREMENT));
      // Spawn new food; a full board ends the game, but still shows the final snake
      spawnFood(outcome.snake, level.walls);
    }

    setSnake(outcome.snake);

  }, [snake, nextDirection, status, food, level]);

  // Place food on a free cell, or end the game when the board is full.
  // Returns false when the game ended.
  const spawnFood = (currentSnake: Point[], currentWalls: Point[]): boolean => {
    const outcome = placeFood(currentSnake, currentWalls);
    if (outcome.status === GameStatus.GAME_OVER) {
      handleGameOver();
      return false;
    }
    setFood(outcome.food);
    return true;
  };

  const handleGameOver = () => {
    setStatus(GameStatus.GAME_OVER);
    if (score > highScore) {
      setHighScore(score);
      // Optional: Save to local storage
      localStorage.setItem('neon-snake-highscore', score.toString());
    }
  };

  // Run Game Loop
  useInterval(gameLoop, status === GameStatus.PLAYING ? speed : null);

  // Initialize High Score
  useEffect(() => {
    const saved = localStorage.getItem('neon-snake-highscore');
    if (saved) setHighScore(parseInt(saved, 10));
  }, []);

  // Handlers
  const handleStart = () => {
    // Reset snake for a fresh start if coming from Game Over or fresh load
    if (status === GameStatus.IDLE || status === GameStatus.GAME_OVER) {
      if (!resetGame()) return;
    }
    setStatus(GameStatus.PLAYING);
  };

  const handlePause = () => setStatus(GameStatus.PAUSED);
  const handleResume = () => setStatus(GameStatus.PLAYING);
  
  // Snake, direction, score and speed back to their start values; food is
  // placed by the caller, against whichever walls apply.
  const resetRound = () => {
    setSnake(INITIAL_SNAKE);
    setDirection(Direction.UP);
    setNextDirection(Direction.UP);
    setScore(0);
    setSpeed(INITIAL_SPEED);
  };

  // Returns false when food could not be placed and the game ended.
  const resetGame = (): boolean => {
    resetRound();
    if (!spawnFood(INITIAL_SNAKE, level.walls)) return false;
    setStatus(GameStatus.IDLE);
    return true;
  };

  const handleReset = () => {
    resetGame();
  };

  const handleGenerateLevel = async (prompt: string) => {
    setStatus(GameStatus.GENERATING_LEVEL);
    setLoadingMessage("Consulting Gemini AI...");
    setErrorMsg(null);
    let ended = false;
    try {
      const newLevel = await generateLevel(prompt);
      setLevel(newLevel);
      resetRound();
      // Place food once, against the new level's walls
      const placement = placeFoodForNewLevel(INITIAL_SNAKE, newLevel.walls);
      if (placement.status === GameStatus.GAME_OVER) {
        handleGameOver();
        ended = true;
      } else {
        setFood(placement.food);
      }
    } catch (e: any) {
      setErrorMsg("Failed to generate level. Using current map.");
      console.error(e);
      // Go back to IDLE
      setStatus(GameStatus.IDLE);
    } finally {
      // A full board already set GAME_OVER; don't overwrite it
      if (!ended) setStatus(GameStatus.IDLE);
      setLoadingMessage('');
    }
  };

  return (
    <div className="min-h-screen bg-dark-bg text-white flex flex-col items-center justify-center p-4 relative overflow-hidden">
      
      {/* Background Decor */}
      <div className="absolute top-0 left-0 w-full h-full pointer-events-none opacity-20">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-neon-blue rounded-full blur-[128px]"></div>
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-neon-pink rounded-full blur-[128px]"></div>
      </div>

      <h1 className="text-4xl md:text-6xl font-display font-bold text-transparent bg-clip-text bg-gradient-to-r from-neon-green via-neon-blue to-neon-pink mb-2 drop-shadow-lg text-center">
        NEON SNAKE AI
      </h1>
      <p className="text-slate-400 mb-8 font-light tracking-wide text-center">
        Powered by Gemini • Generate Custom Levels
      </p>

      {errorMsg && (
         <div className="mb-4 bg-red-900/50 border border-red-500 text-red-200 px-4 py-2 rounded">
           {errorMsg}
         </div>
      )}

      <div className="relative">
        <Grid 
          snake={snake} 
          food={food} 
          walls={level.walls} 
          gridSize={GRID_SIZE} 
        />
        
        {/* Overlays */}
        {(status === GameStatus.GAME_OVER) && (
          <div className="absolute inset-0 bg-black/70 flex flex-col items-center justify-center backdrop-blur-sm z-30 rounded-lg">
            <h2 className="text-5xl font-display text-neon-red drop-shadow-neon-red mb-2">GAME OVER</h2>
            <p className="text-xl text-white mb-6">Score: {score}</p>
            <button 
              onClick={handleStart}
              className="bg-neon-green text-black font-bold py-3 px-8 rounded-full hover:scale-105 transition-transform shadow-neon-green"
            >
              TRY AGAIN
            </button>
          </div>
        )}

        {(status === GameStatus.GENERATING_LEVEL) && (
          <div className="absolute inset-0 bg-black/80 flex flex-col items-center justify-center backdrop-blur-md z-40 rounded-lg border border-neon-blue/30">
            <div className="w-16 h-16 border-4 border-neon-blue border-t-transparent rounded-full animate-spin mb-4"></div>
            <h3 className="text-xl font-display text-neon-blue animate-pulse">{loadingMessage}</h3>
            <p className="text-sm text-slate-400 mt-2">Designing obstacles...</p>
          </div>
        )}
      </div>

      <div className="mt-8 w-full flex justify-center">
        <Controls
          status={status}
          score={score}
          highScore={highScore}
          levelName={level.name}
          onStart={handleStart}
          onPause={handlePause}
          onResume={handleResume}
          onReset={handleReset}
          onGenerateLevel={handleGenerateLevel}
        />
      </div>
      
    </div>
  );
};

export default App;