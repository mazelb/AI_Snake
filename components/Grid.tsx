import React, { useMemo } from 'react';
import { Point, LevelConfig } from '../types';
import { GRID_SIZE } from '../constants';

interface GridProps {
  snake: Point[];
  food: Point;
  walls: Point[];
  gridSize: number;
}

const Grid: React.FC<GridProps> = ({ snake, food, walls, gridSize }) => {
  
  // Create a 1D array representing the cells to map over
  const cells = useMemo(() => {
    return Array.from({ length: gridSize * gridSize }, (_, i) => ({
      x: i % gridSize,
      y: Math.floor(i / gridSize),
    }));
  }, [gridSize]);

  // Helper to check what is at a specific coordinate
  const getCellClass = (x: number, y: number) => {
    // Check for Snake Head
    if (snake[0].x === x && snake[0].y === y) {
      return "bg-neon-green shadow-neon-green z-20 rounded-sm";
    }
    
    // Check for Snake Body
    const isBody = snake.some((s, index) => index !== 0 && s.x === x && s.y === y);
    if (isBody) {
      return "bg-green-500/80 rounded-sm";
    }

    // Check for Food
    if (food.x === x && food.y === y) {
      return "bg-neon-pink shadow-neon-pink rounded-full animate-pulse-fast";
    }

    // Check for Wall
    const isWall = walls.some(w => w.x === x && w.y === y);
    if (isWall) {
      return "bg-slate-600 border border-slate-500 rounded-sm";
    }

    // Empty cell
    return "bg-slate-900/50";
  };

  return (
    <div 
      className="grid gap-px bg-slate-800 border-2 border-slate-700 shadow-2xl rounded-lg overflow-hidden relative"
      style={{
        gridTemplateColumns: `repeat(${gridSize}, minmax(0, 1fr))`,
        width: 'min(90vw, 600px)',
        height: 'min(90vw, 600px)',
      }}
    >
      {cells.map((cell) => {
        const key = `${cell.x}-${cell.y}`;
        const baseClass = "w-full h-full transition-colors duration-75";
        const typeClass = getCellClass(cell.x, cell.y);
        
        return (
          <div 
            key={key} 
            className={`${baseClass} ${typeClass}`}
          />
        );
      })}
    </div>
  );
};

export default Grid;