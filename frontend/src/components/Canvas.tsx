import React, { useMemo } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Node,
  Edge,
  BackgroundVariant,
  OnNodesChange,
  OnEdgesChange,
  NodeMouseHandler,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { CustomNode } from './CustomNode';
import { CustomNodeData } from '../types';

interface CanvasProps {
  nodes: Node<CustomNodeData>[];
  edges: Edge[];
  onNodesChange: OnNodesChange<Node<CustomNodeData>>;
  onEdgesChange: OnEdgesChange;
  onNodeClick: (node: Node<CustomNodeData>) => void;
  theme: 'dark' | 'light';
}

export const Canvas: React.FC<CanvasProps> = ({
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
  onNodeClick,
  theme,
}) => {
  const nodeTypes = useMemo(
    () => ({
      custom: CustomNode,
    }),
    []
  );

  const handleNodeClick: NodeMouseHandler<Node<CustomNodeData>> = (_, node) => {
    onNodeClick(node);
  };

  return (
    <div className="flex-1 w-full h-full relative overflow-hidden bg-background">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.25 }}
        minZoom={0.4}
        maxZoom={1.6}
        defaultEdgeOptions={{
          type: 'smoothstep',
        }}
        proOptions={{ hideAttribution: true }}
      >
        {/* Subtle Dot Grid Background */}
        <Background
          variant={BackgroundVariant.Dots}
          gap={20}
          size={1.2}
          color={theme === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.12)'}
        />

        {/* Viewport Zoom & Pan Controls */}
        <Controls
          position="bottom-left"
          showInteractive={false}
          className="!m-4"
        />

        {/* Corner MiniMap */}
        <MiniMap
          position="bottom-right"
          zoomable
          pannable
          className="!m-4 !hidden md:!block"
          nodeColor={(n) => {
            const data = n.data as unknown as CustomNodeData;
            if (data?.tier === 'small') return '#10b981';
            if (data?.tier === 'medium') return '#f59e0b';
            if (data?.tier === 'large') return '#a855f7';
            return theme === 'dark' ? '#334155' : '#cbd5e1';
          }}
          maskColor={theme === 'dark' ? 'rgba(15, 23, 42, 0.7)' : 'rgba(241, 245, 249, 0.7)'}
        />
      </ReactFlow>
    </div>
  );
};
