"use client";

import React, { useState } from "react";
import { NetworkGraphResponse, NetworkNode } from "../../lib/types";

interface NetworkGraphProps {
  data: NetworkGraphResponse | null;
}

export function NetworkGraph({ data }: NetworkGraphProps) {
  const [selectedNode, setSelectedNode] = useState<NetworkNode | null>(null);

  if (!data) {
    return (
      <div className="flex h-80 items-center justify-center rounded-xl border border-slate-800 bg-slate-900/50 text-xs text-slate-400">
        Loading identity network graph...
      </div>
    );
  }

  // Pre-calculate circular node positions centered on canvas
  const centerX = 300;
  const centerY = 200;
  const radius = 130;

  const nodePositions: Record<string, { x: number; y: number }> = {};
  const otherNodes = data.nodes.filter((n) => n.id !== data.root_user_id);

  nodePositions[data.root_user_id] = { x: centerX, y: centerY };

  otherNodes.forEach((node, i) => {
    const angle = (i / otherNodes.length) * 2 * Math.PI - Math.PI / 2;
    nodePositions[node.id] = {
      x: centerX + radius * Math.cos(angle),
      y: centerY + radius * Math.sin(angle),
    };
  });

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
      {/* Interactive Visual Graph Canvas */}
      <div className="relative overflow-hidden rounded-xl border border-slate-800/80 bg-slate-950 p-4 lg:col-span-2">
        <div className="mb-2 flex items-center justify-between text-xs text-slate-400">
          <span>Identity Graph: {data.nodes.length} Nodes • {data.edges.length} Edges</span>
          <span className="rounded bg-slate-800 px-2 py-0.5 text-[10px] text-blue-400">
            Connected Component Size: {data.summary.connected_component_size}
          </span>
        </div>

        <svg viewBox="0 0 600 400" className="h-80 w-full select-none">
          {/* Edges */}
          {data.edges.map((edge, idx) => {
            const p1 = nodePositions[edge.source] || { x: centerX, y: centerY };
            const p2 = nodePositions[edge.target] || { x: centerX, y: centerY };
            return (
              <g key={`edge-${idx}`}>
                <line
                  x1={p1.x}
                  y1={p1.y}
                  x2={p2.x}
                  y2={p2.y}
                  stroke="#334155"
                  strokeWidth="1.5"
                  strokeDasharray={edge.relation.includes("LINKED") ? "4,4" : undefined}
                />
              </g>
            );
          })}

          {/* Nodes */}
          {data.nodes.map((node) => {
            const pos = nodePositions[node.id] || { x: centerX, y: centerY };
            const isRoot = node.id === data.root_user_id;
            const isSelected = selectedNode?.id === node.id;

            let fillColor = "#3b82f6"; // blue
            if (node.type === "device") fillColor = "#8b5cf6"; // purple
            if (node.type === "address") fillColor = "#f59e0b"; // amber
            if (node.type === "payment") fillColor = "#10b981"; // emerald
            if (node.risk_level === "HIGH") fillColor = "#ef4444"; // red

            return (
              <g
                key={`node-${node.id}`}
                className="cursor-pointer transition-transform duration-150 hover:scale-110"
                onClick={() => setSelectedNode(node)}
              >
                <circle
                  cx={pos.x}
                  cy={pos.y}
                  r={isRoot ? 20 : 15}
                  fill={fillColor}
                  stroke={isSelected ? "#ffffff" : "#0f172a"}
                  strokeWidth={isSelected ? "3" : "2"}
                  opacity="0.9"
                />
                <text
                  x={pos.x}
                  y={pos.y + (isRoot ? 32 : 26)}
                  textAnchor="middle"
                  fill="#94a3b8"
                  fontSize="10"
                  fontWeight="bold"
                >
                  {node.label.length > 16 ? node.label.slice(0, 14) + "…" : node.label}
                </text>
              </g>
            );
          })}
        </svg>

        <div className="flex flex-wrap gap-4 pt-2 border-t border-slate-900 text-[10px] text-slate-400">
          <div className="flex items-center gap-1.5">
            <div className="h-2.5 w-2.5 rounded-full bg-blue-500" />
            <span>Claimant User</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="h-2.5 w-2.5 rounded-full bg-purple-500" />
            <span>Device</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="h-2.5 w-2.5 rounded-full bg-amber-500" />
            <span>Address</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
            <span>Payment</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="h-2.5 w-2.5 rounded-full bg-rose-500" />
            <span>High-Risk Syndicate Node</span>
          </div>
        </div>
      </div>

      {/* Node Inspector Details Panel */}
      <div className="flex flex-col justify-between rounded-xl border border-slate-800/80 bg-slate-900/60 p-5 backdrop-blur-md">
        <div>
          <h4 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
            Node Inspector
          </h4>
          <p className="text-xs text-slate-400 mb-4">Click any graph entity to view linkage metadata</p>

          {selectedNode ? (
            <div className="space-y-3 rounded-lg border border-slate-800 bg-slate-950/70 p-4">
              <div>
                <span className="text-[10px] uppercase font-bold text-slate-400">Identifier</span>
                <p className="font-mono text-sm font-semibold text-white">{selectedNode.id}</p>
              </div>
              <div className="flex justify-between text-xs">
                <div>
                  <span className="text-[10px] uppercase text-slate-400">Entity Type</span>
                  <p className="capitalize font-medium text-slate-200">{selectedNode.type}</p>
                </div>
                <div>
                  <span className="text-[10px] uppercase text-slate-400">Risk Assessment</span>
                  <p className="font-semibold text-rose-400">{selectedNode.risk_level}</p>
                </div>
              </div>
              {selectedNode.properties && Object.keys(selectedNode.properties).length > 0 && (
                <div className="pt-2 border-t border-slate-800">
                  <span className="text-[10px] uppercase text-slate-400">Properties</span>
                  <pre className="mt-1 max-h-24 overflow-y-auto rounded bg-slate-900 p-2 text-[10px] font-mono text-slate-300">
                    {JSON.stringify(selectedNode.properties, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          ) : (
            <div className="rounded-lg border border-dashed border-slate-800 p-6 text-center text-xs text-slate-500">
              Select any graph node to inspect identity relationships.
            </div>
          )}
        </div>

        <div className="mt-4 rounded-lg bg-slate-950/50 p-3 text-xs text-slate-400 border border-slate-800">
          🔍 <strong>Syndicate Linkage</strong>: {data.summary.linked_accounts_count} distinct customer accounts are bound to this entity footprint.
        </div>
      </div>
    </div>
  );
}
