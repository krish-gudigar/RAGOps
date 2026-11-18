import React from 'react';
import { History, Trash2, ArrowUpRight, Zap, Cpu, Sparkles } from 'lucide-react';
import { QueryHistoryItem, Tier } from '../types';

interface HistoryBarProps {
  history: QueryHistoryItem[];
  selectedId: string | null;
  onSelect: (item: QueryHistoryItem) => void;
  onClear: () => void;
}

function getTierBadge(tier: Tier) {
  switch (tier) {
    case 'small':
      return {
        badge: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20',
        icon: <Zap className="w-3 h-3 text-emerald-500" />,
      };
    case 'medium':
      return {
        badge: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20',
        icon: <Cpu className="w-3 h-3 text-amber-500" />,
      };
    case 'large':
      return {
        badge: 'bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20',
        icon: <Sparkles className="w-3 h-3 text-purple-500" />,
      };
  }
}

export const HistoryBar: React.FC<HistoryBarProps> = ({
  history,
  selectedId,
  onSelect,
  onClear,
}) => {
  return (
    <footer className="h-12 px-4 border-t border-border bg-card/85 backdrop-blur-md flex items-center justify-between gap-4 z-20 shrink-0 text-xs">
      {/* Label & Count */}
      <div className="flex items-center gap-2 shrink-0 text-muted-foreground">
        <History className="w-3.5 h-3.5 text-accent" />
        <span className="font-semibold text-foreground text-[11px] uppercase tracking-wider">
          Query Run History
        </span>
        <span className="px-1.5 py-0.2 rounded-full bg-muted text-[10px] font-mono">
          {history.length}
        </span>
      </div>

      {/* Query Pills List (Scrollable) */}
      <div className="flex-1 flex items-center gap-2 overflow-x-auto no-scrollbar py-1">
        {history.length === 0 ? (
          <span className="text-muted-foreground/60 text-[11px] italic">
            Executed queries will appear here in chronological order.
          </span>
        ) : (
          history.map((item) => {
            const { badge, icon } = getTierBadge(item.result.tier);
            const isSelected = selectedId === item.id;

            return (
              <button
                key={item.id}
                onClick={() => onSelect(item)}
                className={`flex items-center gap-2 px-2.5 py-1 rounded-lg border text-left shrink-0 transition-all duration-150 ${
                  isSelected
                    ? 'border-accent bg-accent/10 shadow-sm'
                    : 'border-border bg-background/50 hover:border-foreground/30 hover:bg-muted/50'
                }`}
                title={item.query}
              >
                <span className="flex items-center gap-1">{icon}</span>
                <span className="font-medium text-foreground max-w-[150px] truncate text-[11px]">
                  {item.query}
                </span>
                <span
                  className={`text-[9px] font-mono px-1 py-0.2 rounded border uppercase font-semibold ${badge}`}
                >
                  {item.result.tier}
                </span>
                <span className="text-[10px] text-muted-foreground font-mono">
                  {item.result.latencyMs}ms
                </span>
                <ArrowUpRight className="w-3 h-3 text-muted-foreground/50 opacity-0 group-hover:opacity-100" />
              </button>
            );
          })
        )}
      </div>

      {/* Clear History Button */}
      {history.length > 0 && (
        <button
          onClick={onClear}
          className="p-1 rounded-md text-muted-foreground hover:text-red-500 hover:bg-red-500/10 transition-colors shrink-0"
          title="Clear query history"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      )}
    </footer>
  );
};
