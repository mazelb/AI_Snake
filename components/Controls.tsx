import React, { useState } from 'react';
import { GameStatus } from '../types';

interface ControlsProps {
  status: GameStatus;
  score: number;
  highScore: number;
  levelName: string;
  onStart: () => void;
  onPause: () => void;
  onResume: () => void;
  onReset: () => void;
  onGenerateLevel: (prompt: string) => void;
}

const Controls: React.FC<ControlsProps> = ({
  status,
  score,
  highScore,
  levelName,
  onStart,
  onPause,
  onResume,
  onReset,
  onGenerateLevel,
}) => {
  const [prompt, setPrompt] = useState('');
  const [isPromptOpen, setIsPromptOpen] = useState(false);

  const handleSubmitGen = (e: React.FormEvent) => {
    e.preventDefault();
    if (prompt.trim()) {
      onGenerateLevel(prompt);
      setIsPromptOpen(false);
      setPrompt('');
    }
  };

  return (
    <div className="flex flex-col w-full max-w-[600px] gap-4 p-4 bg-slate-800/50 rounded-xl border border-slate-700 backdrop-blur-sm">
      {/* Score Board */}
      <div className="flex justify-between items-center text-white">
        <div>
          <p className="text-xs text-slate-400 uppercase tracking-wider">Score</p>
          <p className="text-3xl font-display text-neon-green shadow-neon-green drop-shadow-md">{score}</p>
        </div>
        <div className="text-right">
          <p className="text-xs text-slate-400 uppercase tracking-wider">High Score</p>
          <p className="text-xl font-display text-slate-200">{highScore}</p>
        </div>
      </div>

      {/* Level Info */}
      <div className="flex justify-between items-center border-t border-slate-700 pt-3">
        <span className="text-sm text-slate-300">
          Map: <span className="font-semibold text-neon-blue">{levelName}</span>
        </span>
        <button 
          onClick={() => setIsPromptOpen(!isPromptOpen)}
          disabled={status === GameStatus.PLAYING}
          className="text-xs text-neon-pink hover:text-white transition-colors disabled:opacity-50"
        >
          {isPromptOpen ? 'Cancel AI' : '✨ AI Generate Level'}
        </button>
      </div>

      {/* AI Prompt Input */}
      {isPromptOpen && (
        <form onSubmit={handleSubmitGen} className="flex gap-2 animate-in fade-in slide-in-from-top-2">
          <input
            type="text"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="e.g. 'A maze shaped like a skull'"
            className="flex-1 bg-slate-900 border border-slate-600 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-neon-pink"
            autoFocus
          />
          <button
            type="submit"
            className="bg-neon-pink/20 border border-neon-pink text-neon-pink px-4 py-1 rounded text-sm hover:bg-neon-pink hover:text-white transition-all"
          >
            Generate
          </button>
        </form>
      )}

      {/* Main Buttons */}
      <div className="grid grid-cols-2 gap-3 mt-2">
        {status === GameStatus.PLAYING ? (
          <button
            onClick={onPause}
            className="bg-yellow-500/20 border border-yellow-500 text-yellow-500 py-3 rounded-lg font-bold hover:bg-yellow-500 hover:text-black transition-all"
          >
            PAUSE
          </button>
        ) : (
          <button
            onClick={status === GameStatus.PAUSED ? onResume : onStart}
            disabled={status === GameStatus.GENERATING_LEVEL}
            className="bg-neon-green/20 border border-neon-green text-neon-green py-3 rounded-lg font-bold hover:bg-neon-green hover:text-black transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {status === GameStatus.PAUSED ? 'RESUME' : status === GameStatus.GAME_OVER ? 'PLAY AGAIN' : 'START GAME'}
          </button>
        )}
        
        <button
          onClick={onReset}
          disabled={status === GameStatus.PLAYING || status === GameStatus.GENERATING_LEVEL}
          className="bg-slate-700/50 border border-slate-600 text-slate-300 py-3 rounded-lg font-bold hover:bg-slate-600 hover:text-white transition-all disabled:opacity-50"
        >
          RESET
        </button>
      </div>
      
      <div className="text-center text-xs text-slate-500 mt-1">
        Use Arrow Keys or WASD to move
      </div>
    </div>
  );
};

export default Controls;