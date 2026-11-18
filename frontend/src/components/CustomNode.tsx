import { memo } from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import {
  MessageSquare,
  Activity,
  GitFork,
  Cpu,
  Zap,
  Sparkles,
  CheckCircle2,
} from 'lucide-react';
import { CustomNodeData, Tier } from '../types';

function getIcon(nodeType: string) {
  switch (nodeType) {
    case 'query_input':
      return <MessageSquare className="w-4 h-4 text-sky-400" />;
    case 'analyzer':
      return <Activity className="w-4 h-4 text-blue-400" />;
    case 'router':
      return <GitFork className="w-4 h-4 text-indigo-400" />;
    case 'model_small':
      return <Zap className="w-4 h-4 text-emerald-400" />;
    case 'model_medium':
      return <Cpu className="w-4 h-4 text-amber-400" />;
    case 'model_large':
      return <Sparkles className="w-4 h-4 text-purple-400" />;
    case 'response':
      return <CheckCircle2 className="w-4 h-4 text-teal-400" />;
    default:
      return <Activity className="w-4 h-4 text-slate-400" />;
  }
}

function getBadgeStyles(tier?: Tier, nodeType?: string) {
  if (tier === 'small' || nodeType === 'model_small') {
    return {
      border: 'border-emerald-500/30 dark:border-emerald-500/40',
      activeBorder: 'border-emerald-500 ring-2 ring-emerald-500/20 shadow-emerald-500/10',
      badgeBg: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20',
      accentDot: 'bg-emerald-500',
    };
  }
  if (tier === 'medium' || nodeType === 'model_medium') {
    return {
      border: 'border-amber-500/30 dark:border-amber-500/40',
      activeBorder: 'border-amber-500 ring-2 ring-amber-500/20 shadow-amber-500/10',
      badgeBg: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20',
      accentDot: 'bg-amber-500',
    };
  }
  if (tier === 'large' || nodeType === 'model_large') {
    return {
      border: 'border-purple-500/30 dark:border-purple-500/40',
      activeBorder: 'border-purple-500 ring-2 ring-purple-500/20 shadow-purple-500/10',
      badgeBg: 'bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20',
      accentDot: 'bg-purple-500',
    };
  }
  return {
    border: 'border-border',
    activeBorder: 'border-accent ring-2 ring-accent/20 shadow-accent/10',
    badgeBg: 'bg-muted text-foreground border-border',
    accentDot: 'bg-sky-500',
  };
}

export const CustomNode = memo(({ data, selected }: NodeProps) => {
  const nodeData = data as unknown as CustomNodeData;
  const { nodeType, title, subtitle, tier, status, isActivePath, isDimmed } = nodeData;

  const styles = getBadgeStyles(tier, nodeType);

  const isModel = nodeType.startsWith('model_');
  const showTargetHandle = nodeType !== 'query_input';
  const showSourceHandle = nodeType !== 'response';

  return (
    <div
      className={`relative group rounded-xl bg-card text-card-foreground p-3.5 shadow-sm transition-all duration-200 min-w-[210px] max-w-[230px] border ${
        styles.border
      } ${
        isActivePath || selected
          ? `${styles.activeBorder} shadow-md`
          : 'hover:border-foreground/30 hover:shadow'
      } ${isDimmed ? 'opacity-40 grayscale-[20%]' : 'opacity-100'}`}
    >
      {/* Left Input Handle */}
      {showTargetHandle && (
        <Handle
          type="target"
          position={Position.Left}
          className="!w-2.5 !h-2.5 !bg-muted-foreground !border-2 !border-background !rounded-full !-left-1.5 transition-colors group-hover:!bg-accent"
        />
      )}

      {/* Header with Icon, Title, and Status Indicator */}
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-2">
          <div
            className={`w-7 h-7 rounded-lg flex items-center justify-center border ${styles.badgeBg}`}
          >
            {getIcon(nodeType)}
          </div>
          <span className="font-semibold text-xs text-foreground tracking-tight">
            {title}
          </span>
        </div>

        {/* Status Dot */}
        <div className="flex items-center" title={`Status: ${status}`}>
          {status === 'running' ? (
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-sky-500"></span>
            </span>
          ) : status === 'done' ? (
            <span className="h-2 w-2 rounded-full bg-emerald-500 inline-block shadow-sm"></span>
          ) : (
            <span className="h-2 w-2 rounded-full bg-muted-foreground/30 inline-block"></span>
          )}
        </div>
      </div>

      {/* Subtitle / Description */}
      <p className="text-[11px] text-muted-foreground line-clamp-1 pl-0.5">
        {subtitle}
      </p>

      {/* Special Tier Badge for Model Nodes */}
      {isModel && tier && (
        <div className="mt-2.5 pt-2 border-t border-border/50 flex items-center justify-between text-[10px]">
          <span className="text-muted-foreground capitalize font-medium">Tier</span>
          <span
            className={`px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider ${
              tier === 'small'
                ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                : tier === 'medium'
                ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400'
                : 'bg-purple-500/10 text-purple-600 dark:text-purple-400'
            }`}
          >
            {tier}
          </span>
        </div>
      )}

      {/* Right Output Handle */}
      {showSourceHandle && (
        <Handle
          type="source"
          position={Position.Right}
          className="!w-2.5 !h-2.5 !bg-muted-foreground !border-2 !border-background !rounded-full !-right-1.5 transition-colors group-hover:!bg-accent"
        />
      )}
    </div>
  );
});

CustomNode.displayName = 'CustomNode';
