import React, { useState } from 'react';
import { Play, Sun, Moon, Loader2, Compass } from 'lucide-react';

interface TopBarProps {
  onRun: (query: string) => void;
  isRunning: boolean;
  theme: 'dark' | 'light';
  onToggleTheme: () => void;
}

const SAMPLE_QUERIES = [
  { label: 'Small Tier (Easy)', text: 'Translate "Good morning, how are you?" to Spanish.' },
  { label: 'Medium Tier (Code)', text: 'Write a Python function to check if a word is a palindrome, ignoring punctuation.' },
  { label: 'Large Tier (Architecture)', text: 'Design a distributed Raft consensus protocol with leader election and log compaction.' },
];

export const TopBar: React.FC<TopBarProps> = ({
  onRun,
  isRunning,
  theme,
  onToggleTheme,
}) => {
  const [query, setQuery] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || isRunning) return;
    onRun(query);
  };

  const handleSelectSample = (text: string) => {
    setQuery(text);
    onRun(text);
  };

  return (
    <header className="h-16 px-5 border-b border-border bg-card/80 backdrop-blur-md flex items-center justify-between gap-4 z-20 shrink-0">
      {/* Left: Branding */}
      <div className="flex items-center gap-3 shrink-0">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-sky-500 to-indigo-600 flex items-center justify-center text-white shadow-sm shadow-sky-500/20">
          <Compass className="w-5 h-5" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="font-bold text-base tracking-tight text-foreground">
              RouteWise
            </span>
            <span className="text-[10px] uppercase font-semibold tracking-wider px-1.5 py-0.5 rounded bg-sky-500/10 text-sky-600 dark:text-sky-400 border border-sky-500/20">
              v1.0
            </span>
          </div>
          <p className="text-[11px] text-muted-foreground hidden sm:block">
            Intelligent LLM Cost & Difficulty Router
          </p>
        </div>
      </div>

      {/* Center: Query Input Form */}
      <form
        onSubmit={handleSubmit}
        className="flex-1 max-w-2xl flex items-center gap-2 relative"
      >
        <div className="relative flex-1">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={isRunning}
            placeholder="Enter a prompt to analyze, score difficulty, and route..."
            className="w-full h-10 pl-3.5 pr-20 text-xs sm:text-sm rounded-xl border border-border bg-background text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent transition-all duration-150 disabled:opacity-60"
          />
          <div className="absolute right-2.5 top-1/2 -translate-y-1/2 flex items-center gap-1.5 pointer-events-none">
            <kbd className="hidden sm:inline-block text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-muted text-muted-foreground border border-border">
              Enter
            </kbd>
          </div>
        </div>

        <button
          type="submit"
          disabled={!query.trim() || isRunning}
          className="h-10 px-4 rounded-xl font-medium text-xs sm:text-sm bg-accent text-accent-foreground hover:bg-accent/90 disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2 shadow-sm transition-all duration-150 shrink-0"
        >
          {isRunning ? (
            <>
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              <span>Routing...</span>
            </>
          ) : (
            <>
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>Run</span>
            </>
          )}
        </button>
      </form>

      {/* Right: Quick Samples & Theme Toggle */}
      <div className="flex items-center gap-2 shrink-0">
        {/* Sample presets dropdown / pill */}
        <div className="hidden lg:flex items-center gap-1.5 text-xs">
          <span className="text-[11px] text-muted-foreground mr-1">Presets:</span>
          {SAMPLE_QUERIES.map((sample, idx) => (
            <button
              key={idx}
              type="button"
              disabled={isRunning}
              onClick={() => handleSelectSample(sample.text)}
              className="text-[11px] px-2 py-1 rounded-lg border border-border/70 hover:border-accent hover:text-accent bg-muted/40 hover:bg-muted transition-colors disabled:opacity-40"
            >
              {sample.label.split(' ')[0]}
            </button>
          ))}
        </div>

        {/* Theme Toggle Button */}
        <button
          type="button"
          onClick={onToggleTheme}
          title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          className="w-9 h-9 rounded-xl border border-border bg-card flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
        >
          {theme === 'dark' ? (
            <Sun className="w-4 h-4 text-amber-400" />
          ) : (
            <Moon className="w-4 h-4 text-indigo-500" />
          )}
        </button>
      </div>
    </header>
  );
};
