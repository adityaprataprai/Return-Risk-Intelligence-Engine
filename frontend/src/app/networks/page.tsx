"use client";

import React, { useState } from "react";
import { NetworkGraph } from "../../components/dashboard/NetworkGraph";
import { useNetwork } from "../../hooks/useNetwork";

export default function NetworkExplorerPage() {
  const [selectedCase, setSelectedCase] = useState("ret_demo_block_002");
  const { network, loading } = useNetwork(selectedCase);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Identity Abuse Network Explorer</h1>
          <p className="text-xs text-slate-400 mt-1">
            Traverse multi-account syndicates, shared hardware fingerprints, and address clusters.
          </p>
        </div>

        {/* Case Selector */}
        <div className="flex items-center gap-2 text-xs">
          <span className="text-slate-400 font-medium">Investigate Syndicate:</span>
          <select
            value={selectedCase}
            onChange={(e) => setSelectedCase(e.target.value)}
            className="rounded-lg border border-slate-800 bg-slate-900 px-3 py-1.5 font-mono text-xs text-white outline-none focus:border-blue-500"
          >
            <option value="ret_demo_block_002">ret_demo_block_002 (Syndicate Cluster)</option>
            <option value="ret_demo_high_001">ret_demo_high_001 (Device Cluster)</option>
            <option value="ret_demo_approve_003">ret_demo_approve_003 (Clean User)</option>
          </select>
        </div>
      </div>

      {/* Network Overview Stats */}
      {network && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
            <span className="text-[10px] font-semibold uppercase text-slate-400">Component Size</span>
            <p className="text-xl font-bold text-white">{network.summary.connected_component_size}</p>
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
            <span className="text-[10px] font-semibold uppercase text-slate-400">Linked Accounts</span>
            <p className="text-xl font-bold text-amber-400">{network.summary.linked_accounts_count}</p>
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
            <span className="text-[10px] font-semibold uppercase text-slate-400">Shared Hardware</span>
            <p className="text-xl font-bold text-purple-400">{network.summary.shared_devices_count} Device(s)</p>
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
            <span className="text-[10px] font-semibold uppercase text-slate-400">Graph Anomaly</span>
            <p className="text-xs font-bold text-rose-400 mt-1">
              {network.summary.graph_anomaly_flag ? "HIGH ABUSE RISK" : "NORMAL FOOTPRINT"}
            </p>
          </div>
        </div>
      )}

      {/* Graph Visualizer Canvas */}
      <NetworkGraph data={network} />
    </div>
  );
}
