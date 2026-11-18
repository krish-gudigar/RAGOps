import React from 'react';
import {
  X,
  Gauge,
  Cpu,
  Clock,
  DollarSign,
  Binary,
  Layers,
  HelpCircle,
  FileText,
  CheckCircle,
  Wifi,
  WifiOff,
} from 'lucide-react';
import { CustomNodeData, RouteResult } from '../types';

interface SidePanelProps {
  isOpen: boolean;
  onClose: () => void;
  selectedNodeData: CustomNodeData | null;
  activeResult: RouteResult | null;
  currentQuery: string;
}

export const SidePanel: React.FC<SidePanelProps> = ({
  isOpen,
  onClose,
  selectedNodeData,
  activeResult,
  currentQuery,
}) => {
  if (!isOpen) return null;

  const result = selectedNodeData?.result || activeResult;

  const getDifficultyColor = (score: number) => {
    if (score < 40) return 'text-emerald-500 bg-emerald-500/10 border-emerald-500/20';
    if (score < 75) return 'text-amber-500 bg-amber-500/10 border-amber-500/20';
    return 'text-purple-500 bg-purple-500/10 border-purple-500/20';
  };

  const getDifficultyBarColor = (score: number) => {
    if (score < 40) return 'bg-emerald-500';
    if (score < 75) return 'bg-amber-500';
    return 'bg-purple-500';
  };

  return (
    <aside className="w-80 md:w-96 border-l border-border bg-card/95 backdrop-blur-md flex flex-col h-full z-20 shrink-0 shadow-xl transition-all duration-200">
      {/* Panel Header */}
      <div className="p-4 border-b border-border flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
            <span>Node Inspector</span>
            {selectedNodeData && (
              <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-muted text-muted-foreground border border-border">
                {selectedNodeData.title}
              </span>
            )}
          </h2>
          <p className="text-[11px] text-muted-foreground">
            Telemetry, routing rationale & performance metrics
          </p>
        </div>
        <button
          onClick={onClose}
          className="w-7 h-7 rounded-lg border border-border flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          title="Close details panel"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Content Container */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs">
        {/* Active Query Card */}
        <div className="rounded-xl border border-border bg-background/50 p-3">
          <div className="flex items-center justify-between mb-1 text-[11px] text-muted-foreground font-medium">
            <span>Query Ingested</span>
            <span className="text-[10px] font-mono">{currentQuery ? `${currentQuery.length} chars` : 'Empty'}</span>
          </div>
          <p className="text-foreground text-xs font-mono line-clamp-3 bg-muted/30 p-2 rounded-lg border border-border/50">
            {currentQuery || 'No active query run yet.'}
          </p>
        </div>

        {result ? (
          <>
            {/* Difficulty Score Card */}
            <div className="rounded-xl border border-border bg-card p-3.5 space-y-2.5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5 text-foreground font-medium">
                  <Gauge className="w-4 h-4 text-sky-400" />
                  <span>Difficulty Score</span>
                </div>
                <div
                  className={`text-xs font-bold px-2 py-0.5 rounded-full border ${getDifficultyColor(
                    result.difficulty
                  )}`}
                >
                  {result.difficulty} / 100
                </div>
              </div>

              {/* Progress Bar */}
              <div className="w-full bg-muted rounded-full h-2 overflow-hidden">
                <div
                  className={`h-full transition-all duration-300 rounded-full ${getDifficultyBarColor(
                    result.difficulty
                  )}`}
                  style={{ width: `${Math.min(100, Math.max(5, result.difficulty))}%` }}
                />
              </div>

              {/* 5-Factor Score Matrix */}
              <div className="pt-2 border-t border-border/50 grid grid-cols-5 gap-1 text-center">
                {[
                  { label: 'Cmplx', val: result.scores.complexity },
                  { label: 'Reas', val: result.scores.reasoning },
                  { label: 'Ctxt', val: result.scores.context },
                  { label: 'Cnstr', val: result.scores.constraints },
                  { label: 'Relia', val: result.scores.reliability },
                ].map((s, i) => (
                  <div key={i} className="bg-muted/40 p-1.5 rounded-lg border border-border/40">
                    <span className="block text-[9px] text-muted-foreground uppercase">{s.label}</span>
                    <span className="font-semibold text-foreground text-xs">{s.val}/2</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Model & Tier Rationale */}
            <div className="rounded-xl border border-border bg-card p-3.5 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground font-medium flex items-center gap-1.5">
                  <Cpu className="w-3.5 h-3.5 text-accent" />
                  Selected Tier
                </span>
                <span
                  className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md ${
                    result.tier === 'small'
                      ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20'
                      : result.tier === 'medium'
                      ? 'bg-amber-500/10 text-amber-500 border border-amber-500/20'
                      : 'bg-purple-500/10 text-purple-500 border border-purple-500/20'
                  }`}
                >
                  {result.tier} Tier
                </span>
              </div>
              <div className="font-semibold text-foreground text-xs">{result.model}</div>
              <p className="text-muted-foreground text-[11px] leading-relaxed bg-muted/30 p-2.5 rounded-lg border border-border/40">
                {result.reason}
              </p>
            </div>

            {/* Telemetry Grid (Latency, Cost, Tokens) */}
            <div className="grid grid-cols-2 gap-2">
              <div className="rounded-xl border border-border bg-card p-3">
                <div className="text-[10px] text-muted-foreground flex items-center gap-1 mb-1">
                  <Clock className="w-3 h-3 text-sky-400" />
                  <span>Latency</span>
                </div>
                <div className="text-sm font-bold text-foreground font-mono">
                  {result.latencyMs} <span className="text-[10px] font-normal text-muted-foreground">ms</span>
                </div>
              </div>

              <div className="rounded-xl border border-border bg-card p-3">
                <div className="text-[10px] text-muted-foreground flex items-center gap-1 mb-1">
                  <DollarSign className="w-3 h-3 text-emerald-400" />
                  <span>Est. Cost</span>
                </div>
                <div className="text-sm font-bold text-foreground font-mono">
                  ${result.cost.toFixed(5)}
                </div>
              </div>

              <div className="rounded-xl border border-border bg-card p-3">
                <div className="text-[10px] text-muted-foreground flex items-center gap-1 mb-1">
                  <Binary className="w-3 h-3 text-indigo-400" />
                  <span>Input Tokens</span>
                </div>
                <div className="text-sm font-bold text-foreground font-mono">
                  {result.tokenCount.input}
                </div>
              </div>

              <div className="rounded-xl border border-border bg-card p-3">
                <div className="text-[10px] text-muted-foreground flex items-center gap-1 mb-1">
                  <Layers className="w-3 h-3 text-purple-400" />
                  <span>Output Tokens</span>
                </div>
                <div className="text-sm font-bold text-foreground font-mono">
                  {result.tokenCount.output}
                </div>
              </div>
            </div>

            {/* Response Preview Section */}
            <div className="rounded-xl border border-border bg-card p-3.5 space-y-2">
              <div className="flex items-center justify-between text-muted-foreground font-medium text-[11px]">
                <span className="flex items-center gap-1.5">
                  <FileText className="w-3.5 h-3.5 text-teal-400" />
                  Response Output
                </span>
                <div className="flex items-center gap-2">
                  {result.source === 'backend' ? (
                    <span className="text-[10px] text-emerald-500 flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-emerald-500/10 border border-emerald-500/20">
                      <Wifi className="w-3 h-3" /> Backend · Ollama
                    </span>
                  ) : (
                    <span className="text-[10px] text-amber-400 flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-amber-500/10 border border-amber-500/20">
                      <WifiOff className="w-3 h-3" /> Simulation
                    </span>
                  )}
                  <span className="text-[10px] text-emerald-500 flex items-center gap-1">
                    <CheckCircle className="w-3 h-3" /> Validated
                  </span>
                </div>
              </div>
              <pre className="text-[11px] font-mono text-foreground bg-muted/30 p-2.5 rounded-lg border border-border/40 overflow-x-auto whitespace-pre-wrap max-h-48 leading-relaxed">
                {result.responseText}
              </pre>
            </div>
          </>
        ) : (
          <div className="rounded-xl border border-dashed border-border p-6 text-center text-muted-foreground space-y-2">
            <HelpCircle className="w-8 h-8 mx-auto text-muted-foreground/40" />
            <p className="font-medium text-xs">No execution telemetry yet</p>
            <p className="text-[11px] text-muted-foreground/70">
              Run a prompt using the top bar to watch the workflow execute and populate node stats.
            </p>
          </div>
        )}
      </div>
    </aside>
  );
};
