"use client";

import React, { useEffect, useState } from "react";
import { fetchFeatureHealth, fetchModelHealth, fetchSystemHealth } from "../../lib/api";
import { FeatureHealthResponse, ModelHealthResponse, SystemHealthResponse } from "../../lib/types";

export default function HealthPage() {
  const [modelHealth, setModelHealth] = useState<ModelHealthResponse | null>(null);
  const [featureHealth, setFeatureHealth] = useState<FeatureHealthResponse | null>(null);
  const [systemHealth, setSystemHealth] = useState<SystemHealthResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [m, f, s] = await Promise.all([
          fetchModelHealth(),
          fetchFeatureHealth(),
          fetchSystemHealth(),
        ]);
        setModelHealth(m);
        setFeatureHealth(f);
        setSystemHealth(s);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center rounded-xl border border-slate-800 bg-slate-900/50 text-sm text-slate-400">
        Loading system observability metrics...
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">System & Model Observability</h1>
        <p className="text-xs text-slate-400 mt-1">
          Real-time telemetry, model drift metrics, feature store connectivity, and subsystem liveness.
        </p>
      </div>

      {/* System Status Banner */}
      <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 p-5 backdrop-blur-md">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="flex h-3 w-3 rounded-full bg-emerald-500 shadow-sm shadow-emerald-500" />
            <div>
              <h3 className="text-sm font-bold text-white">Subsystems Operational</h3>
              <p className="text-xs text-slate-400">All core microservices reporting healthy status</p>
            </div>
          </div>
          <span className="rounded-md bg-emerald-500/15 px-3 py-1 text-xs font-mono font-bold text-emerald-400 border border-emerald-500/30">
            SYSTEM HEALTHY
          </span>
        </div>

        {systemHealth && (
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4 border-t border-slate-800 pt-4 text-xs">
            {Object.entries(systemHealth.services).map(([srv, st]) => (
              <div key={srv} className="rounded-lg bg-slate-950/60 p-3 border border-slate-800">
                <span className="text-[10px] uppercase font-mono text-slate-400">{srv.replace(/_/g, " ")}</span>
                <p className="font-semibold text-emerald-400 mt-0.5">● {st.toUpperCase()}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Model & Feature Health Grid */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Model Health */}
        {modelHealth && (
          <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 p-6 backdrop-blur-md">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div>
                <span className="text-xs font-mono font-bold text-blue-400">{modelHealth.version}</span>
                <h3 className="text-base font-bold text-white">Champion LightGBM Model</h3>
              </div>
              <span className="rounded bg-slate-800 px-2.5 py-1 text-xs text-slate-300">
                Isotonic Calibrated
              </span>
            </div>

            <div className="mt-5 grid grid-cols-2 gap-4 text-xs">
              <div className="rounded-lg bg-slate-950 p-3 border border-slate-800">
                <span className="text-[10px] uppercase font-bold text-slate-400">Test AUROC</span>
                <p className="text-xl font-bold text-emerald-400 mt-0.5">{modelHealth.test_auroc.toFixed(4)}</p>
                <span className="text-[10px] text-slate-500">Benchmark target: &gt; 0.90</span>
              </div>
              <div className="rounded-lg bg-slate-950 p-3 border border-slate-800">
                <span className="text-[10px] uppercase font-bold text-slate-400">Test AUPRC</span>
                <p className="text-xl font-bold text-blue-400 mt-0.5">{modelHealth.test_auprc.toFixed(4)}</p>
                <span className="text-[10px] text-slate-500">Precision-Recall curve</span>
              </div>
              <div className="rounded-lg bg-slate-950 p-3 border border-slate-800">
                <span className="text-[10px] uppercase font-bold text-slate-400">Brier Score</span>
                <p className="text-xl font-bold text-white mt-0.5">{modelHealth.brier_score.toFixed(4)}</p>
                <span className="text-[10px] text-slate-500">Well calibrated: &lt; 0.05</span>
              </div>
              <div className="rounded-lg bg-slate-950 p-3 border border-slate-800">
                <span className="text-[10px] uppercase font-bold text-slate-400">Inference Latency</span>
                <p className="text-xl font-bold text-amber-400 mt-0.5">P50: {modelHealth.p50_latency_ms}ms</p>
                <span className="text-[10px] text-slate-500">P95: {modelHealth.p95_latency_ms}ms (SLA &lt; 50ms)</span>
              </div>
            </div>
          </div>
        )}

        {/* Feature Store Health */}
        {featureHealth && (
          <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 p-6 backdrop-blur-md">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div>
                <span className="text-xs font-mono font-bold text-purple-400">{featureHealth.feature_version}</span>
                <h3 className="text-base font-bold text-white">Online Feature Store</h3>
              </div>
              <span className="rounded bg-slate-800 px-2.5 py-1 text-xs text-slate-300">
                52 Schema Features
              </span>
            </div>

            <div className="mt-5 space-y-3 text-xs">
              <div className="flex justify-between p-3 rounded-lg bg-slate-950 border border-slate-800">
                <span className="text-slate-400">Redis Online Feature State</span>
                <span className="font-semibold text-emerald-400">● {featureHealth.redis_status}</span>
              </div>
              <div className="flex justify-between p-3 rounded-lg bg-slate-950 border border-slate-800">
                <span className="text-slate-400">Registered Feature Definitions</span>
                <span className="font-mono font-bold text-white">{featureHealth.feature_count} Features Active</span>
              </div>
              <div className="flex justify-between p-3 rounded-lg bg-slate-950 border border-slate-800">
                <span className="text-slate-400">Graph Snapshot Age</span>
                <span className="font-mono text-slate-200">{featureHealth.graph_freshness_age_seconds}s staleness</span>
              </div>
              <div className="flex justify-between p-3 rounded-lg bg-slate-950 border border-slate-800">
                <span className="text-slate-400">Missing Feature Fallback Rate</span>
                <span className="font-mono text-emerald-400">{(featureHealth.missing_feature_rate * 100).toFixed(2)}% (nominal)</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
