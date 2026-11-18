import { useState, useEffect, useCallback } from 'react';
import { Node, Edge, useNodesState, useEdgesState } from '@xyflow/react';
import { TopBar } from './components/TopBar';
import { Canvas } from './components/Canvas';
import { SidePanel } from './components/SidePanel';
import { HistoryBar } from './components/HistoryBar';
import { routeQuery } from './api';
import { CustomNodeData, QueryHistoryItem, RouteResult, Tier } from './types';

// Initial workflow graph structure
const INITIAL_NODES: Node<CustomNodeData>[] = [
  {
    id: 'query_input',
    type: 'custom',
    position: { x: 50, y: 220 },
    data: {
      nodeType: 'query_input',
      title: 'Query Input',
      subtitle: 'Ingest raw user prompt',
      status: 'idle',
    },
  },
  {
    id: 'analyzer',
    type: 'custom',
    position: { x: 340, y: 220 },
    data: {
      nodeType: 'analyzer',
      title: 'Difficulty Analyzer',
      subtitle: 'Evaluate 5-factor complexity',
      status: 'idle',
    },
  },
  {
    id: 'router',
    type: 'custom',
    position: { x: 630, y: 220 },
    data: {
      nodeType: 'router',
      title: 'Cost & Tier Router',
      subtitle: 'Select optimal capability tier',
      status: 'idle',
    },
  },
  {
    id: 'model_small',
    type: 'custom',
    position: { x: 920, y: 80 },
    data: {
      nodeType: 'model_small',
      title: 'Small Model',
      subtitle: 'qwen2.5:0.5b • Local',
      tier: 'small',
      status: 'idle',
    },
  },
  {
    id: 'model_medium',
    type: 'custom',
    position: { x: 920, y: 220 },
    data: {
      nodeType: 'model_medium',
      title: 'Medium Model',
      subtitle: 'qwen2.5:1.5b • Local',
      tier: 'medium',
      status: 'idle',
    },
  },
  {
    id: 'model_large',
    type: 'custom',
    position: { x: 920, y: 360 },
    data: {
      nodeType: 'model_large',
      title: 'Large Model',
      subtitle: 'qwen2.5:3b • Local',
      tier: 'large',
      status: 'idle',
    },
  },
  {
    id: 'response',
    type: 'custom',
    position: { x: 1220, y: 220 },
    data: {
      nodeType: 'response',
      title: 'Response & Validation',
      subtitle: 'Verify syntax & deliver output',
      status: 'idle',
    },
  },
];

const INITIAL_EDGES: Edge[] = [
  { id: 'e-input-analyzer', source: 'query_input', target: 'analyzer', type: 'smoothstep' },
  { id: 'e-analyzer-router', source: 'analyzer', target: 'router', type: 'smoothstep' },
  { id: 'e-router-small', source: 'router', target: 'model_small', type: 'smoothstep' },
  { id: 'e-router-medium', source: 'router', target: 'model_medium', type: 'smoothstep' },
  { id: 'e-router-large', source: 'router', target: 'model_large', type: 'smoothstep' },
  { id: 'e-small-response', source: 'model_small', target: 'response', type: 'smoothstep' },
  { id: 'e-medium-response', source: 'model_medium', target: 'response', type: 'smoothstep' },
  { id: 'e-large-response', source: 'model_large', target: 'response', type: 'smoothstep' },
];

function getTierColor(tier: Tier) {
  if (tier === 'small') return '#10b981'; // emerald
  if (tier === 'medium') return '#f59e0b'; // amber
  return '#a855f7'; // purple
}

export function App() {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node<CustomNodeData>>(INITIAL_NODES);
  const [edges, setEdges, onEdgesChange] = useEdgesState(INITIAL_EDGES);

  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  const [isRunning, setIsRunning] = useState(false);
  const [executionError, setExecutionError] = useState<string | null>(null);
  const [currentQuery, setCurrentQuery] = useState('');
  const [activeResult, setActiveResult] = useState<RouteResult | null>(null);
  const [selectedNodeData, setSelectedNodeData] = useState<CustomNodeData | null>(null);
  const [isSidePanelOpen, setIsSidePanelOpen] = useState(false);
  const [history, setHistory] = useState<QueryHistoryItem[]>([]);
  const [selectedHistoryId, setSelectedHistoryId] = useState<string | null>(null);

  // Sync theme with HTML document class
  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
      root.classList.remove('light');
    } else {
      root.classList.add('light');
      root.classList.remove('dark');
    }
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

  // Sequentially animate the workflow execution along the chosen route
  const handleRun = useCallback(
    async (query: string) => {
      if (isRunning || !query.trim()) return;

      setIsRunning(true);
      setExecutionError(null);
      setActiveResult(null);
      setSelectedNodeData(null);
      setCurrentQuery(query);
      setSelectedHistoryId(null);

      try {
        // Reset nodes and edges to default state
        setNodes((nds) =>
          nds.map((n) => ({
            ...n,
            data: {
              ...n.data,
              status: 'idle',
              isActivePath: false,
              isDimmed: false,
              currentQuery: query,
            },
          }))
        );
        setEdges((eds) =>
          eds.map((e) => ({
            ...e,
            animated: false,
            className: '',
            style: { stroke: '#475569', strokeWidth: 1.5, opacity: 0.6 },
          }))
        );

        // Step 1: Query Input Processing
        setNodes((nds) =>
          nds.map((n) =>
            n.id === 'query_input'
              ? { ...n, data: { ...n.data, status: 'running', isActivePath: true } }
              : n
          )
        );
        await sleep(180);

        setNodes((nds) =>
          nds.map((n) =>
            n.id === 'query_input' ? { ...n, data: { ...n.data, status: 'done' } } : n
          )
        );

        // Step 2: Analyzer Running
        setEdges((eds) =>
          eds.map((e) =>
            e.id === 'e-input-analyzer'
              ? {
                  ...e,
                  animated: true,
                  className: 'animated-edge',
                  style: { stroke: '#38bdf8', strokeWidth: 2.5, opacity: 1 },
                }
              : e
          )
        );
        setNodes((nds) =>
          nds.map((n) =>
            n.id === 'analyzer'
              ? { ...n, data: { ...n.data, status: 'running', isActivePath: true } }
              : n
          )
        );

        // Fetch the route decision from the backend.
        const result = await routeQuery(query);
        setActiveResult(result);

        await sleep(220);
        setNodes((nds) =>
          nds.map((n) =>
            n.id === 'analyzer'
              ? { ...n, data: { ...n.data, status: 'done', result } }
              : n
          )
        );

        // Step 3: Router Running
        setEdges((eds) =>
          eds.map((e) =>
            e.id === 'e-analyzer-router'
              ? {
                  ...e,
                  animated: true,
                  className: 'animated-edge',
                  style: { stroke: '#818cf8', strokeWidth: 2.5, opacity: 1 },
                }
              : e
          )
        );
        setNodes((nds) =>
          nds.map((n) =>
            n.id === 'router'
              ? { ...n, data: { ...n.data, status: 'running', isActivePath: true, result } }
              : n
          )
        );
        await sleep(200);

        setNodes((nds) =>
          nds.map((n) =>
            n.id === 'router' ? { ...n, data: { ...n.data, status: 'done' } } : n
          )
        );

        // Step 4: Chosen Model Running (Unchosen models dimmed to 40% opacity)
        const targetModelId =
          result.tier === 'small'
            ? 'model_small'
            : result.tier === 'medium'
            ? 'model_medium'
            : 'model_large';

        const tierColor = getTierColor(result.tier);

        setEdges((eds) =>
          eds.map((e) => {
            if (e.id === `e-router-${result.tier}`) {
              return {
                ...e,
                animated: true,
                className: 'animated-edge',
                style: { stroke: tierColor, strokeWidth: 2.5, opacity: 1 },
              };
            }
            if (e.source === 'router') {
              return { ...e, style: { stroke: '#334155', strokeWidth: 1, opacity: 0.2 } };
            }
            return e;
          })
        );

        setNodes((nds) =>
          nds.map((n) => {
            if (n.id === targetModelId) {
              return {
                ...n,
                data: {
                  ...n.data,
                  status: 'running',
                  isActivePath: true,
                  isDimmed: false,
                  result,
                },
              };
            }
            if (n.id.startsWith('model_')) {
              return {
                ...n,
                data: { ...n.data, isDimmed: true, status: 'idle' },
              };
            }
            return n;
          })
        );

        await sleep(240);

        setNodes((nds) =>
          nds.map((n) =>
            n.id === targetModelId
              ? { ...n, data: { ...n.data, status: 'done' } }
              : n
          )
        );

        // Step 5: Response & Validation Output
        setEdges((eds) =>
          eds.map((e) => {
            if (e.id === `e-${result.tier}-response`) {
              return {
                ...e,
                animated: true,
                className: 'animated-edge',
                style: { stroke: tierColor, strokeWidth: 2.5, opacity: 1 },
              };
            }
            if (e.target === 'response') {
              return { ...e, style: { stroke: '#334155', strokeWidth: 1, opacity: 0.2 } };
            }
            return e;
          })
        );

        setNodes((nds) =>
          nds.map((n) =>
            n.id === 'response'
              ? {
                  ...n,
                  data: {
                    ...n.data,
                    status: 'running',
                    isActivePath: true,
                    result,
                  },
                }
              : n
          )
        );

        await sleep(200);

        setNodes((nds) =>
          nds.map((n) =>
            n.id === 'response'
              ? { ...n, data: { ...n.data, status: 'done' } }
              : n
          )
        );

        // Add to history
        const historyItem: QueryHistoryItem = {
          id: `hist-${Date.now()}`,
          query,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          result,
        };

        setHistory((prev) => [historyItem, ...prev.slice(0, 9)]);
        setSelectedHistoryId(historyItem.id);
        setIsSidePanelOpen(true);
      } catch (error) {
        console.error('[RouteWise] Workflow execution error:', error);
        setExecutionError(
          error instanceof Error ? error.message : 'The workflow execution failed.'
        );
      } finally {
        setIsRunning(false);
      }
    },
    [isRunning, setNodes, setEdges]
  );

  // Handle clicking a node to inspect details in SidePanel
  const handleNodeClick = useCallback((node: Node<CustomNodeData>) => {
    setSelectedNodeData(node.data);
    setIsSidePanelOpen(true);
  }, []);

  // Replay/view a previous history item
  const handleSelectHistory = useCallback(
    (item: QueryHistoryItem) => {
      setSelectedHistoryId(item.id);
      setSelectedNodeData(null);
      setCurrentQuery(item.query);
      setActiveResult(item.result);
      setIsSidePanelOpen(true);

      const targetModelId =
        item.result.tier === 'small'
          ? 'model_small'
          : item.result.tier === 'medium'
          ? 'model_medium'
          : 'model_large';

      const tierColor = getTierColor(item.result.tier);

      setNodes((nds) =>
        nds.map((n) => {
          const isTargetModel = n.id === targetModelId;
          const isOtherModel = n.id.startsWith('model_') && !isTargetModel;
          const isCorePath = ['query_input', 'analyzer', 'router', 'response'].includes(n.id);

          return {
            ...n,
            data: {
              ...n.data,
              status: isTargetModel || isCorePath ? 'done' : 'idle',
              isActivePath: isTargetModel || isCorePath,
              isDimmed: isOtherModel,
              result: item.result,
              currentQuery: item.query,
            },
          };
        })
      );

      setEdges((eds) =>
        eds.map((e) => {
          if (
            e.id === 'e-input-analyzer' ||
            e.id === 'e-analyzer-router' ||
            e.id === `e-router-${item.result.tier}` ||
            e.id === `e-${item.result.tier}-response`
          ) {
            return {
              ...e,
              animated: true,
              className: 'animated-edge',
              style: { stroke: tierColor, strokeWidth: 2.2, opacity: 1 },
            };
          }
          return {
            ...e,
            animated: false,
            className: '',
            style: { stroke: '#334155', strokeWidth: 1, opacity: 0.2 },
          };
        })
      );
    },
    [setNodes, setEdges]
  );

  const handleClearHistory = () => {
    setHistory([]);
    setSelectedHistoryId(null);
  };

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-background text-foreground font-sans">
      {/* Top Navigation & Query Runner */}
      <TopBar
        onRun={handleRun}
        isRunning={isRunning}
        theme={theme}
        onToggleTheme={toggleTheme}
      />
      {executionError && (
        <div
          role="alert"
          className="border-b border-red-500/30 bg-red-500/10 px-4 py-2 text-sm text-red-400"
        >
          Backend execution failed: {executionError}
        </div>
      )}

      {/* Main Interactive Workflow Area */}
      <main className="flex-1 flex w-full relative overflow-hidden">
        <Canvas
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={handleNodeClick}
          theme={theme}
        />

        {/* Collapsible Node Inspector Panel */}
        <SidePanel
          isOpen={isSidePanelOpen}
          onClose={() => setIsSidePanelOpen(false)}
          selectedNodeData={selectedNodeData}
          activeResult={activeResult}
          currentQuery={currentQuery}
        />
      </main>

      {/* Bottom History Strip */}
      <HistoryBar
        history={history}
        selectedId={selectedHistoryId}
        onSelect={handleSelectHistory}
        onClear={handleClearHistory}
      />
    </div>
  );
}

export default App;
