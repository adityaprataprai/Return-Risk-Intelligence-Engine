"use client";

import React, { useEffect, useState } from "react";
import { fetchPolicies, simulatePolicy } from "../../lib/api";
import { PolicyConfig, PolicySimulateResponse } from "../../lib/types";
import { formatCurrency } from "../../lib/utils";

export default function PoliciesPage() {
  const [policy, setPolicy] = useState<PolicyConfig | null>(null);
  const [verifyThreshold, setVerifyThreshold] = useState(0.40);
  const [blockThreshold, setBlockThreshold] = useState(0.80);
  const [simulation, setSimulation] = useState<PolicySimulateResponse | null>(null);
  const [simulating, setSimulating] = useState(false);

  useEffect(() => {
    async function load() {
      const p = await fetchPolicies();
      setPolicy(p);
      setVerifyThreshold(p.verify_threshold);
      setBlockThreshold(p.block_threshold);

      // Initial simulation
      const sim = await simulatePolicy(p.verify_threshold, p.block_threshold);
      setSimulation(sim);
    }
    load();
  }, []);

  const handleRunSimulation = async () => {
    setSimulating(true);
    try {
      const sim = await simulatePolicy(verifyThreshold, blockThreshold);
      setSimulation(sim);
    } finally {
      setSimulating(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">Policy Engine & Simulation Sandbox</h1>
        <p className="text-xs text-slate-400 mt-1">
          Review active automated decision rulebooks and simulate threshold adjustments on historical return cohorts.
        </p>
      </div>

      {/* Active Policy Rules Card */}
      {policy && (
        <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 p-6 backdrop-blur-md">
          <div className="flex items-center justify-between pb-4 border-b border-slate-800">
            <div>
              <span className="text-xs font-mono font-semibold text-blue-400">{policy.version}</span>
              <h3 className="text-base font-bold text-white">Standard Risk Rulebook</h3>
            </div>
            <span className="rounded-md bg-emerald-500/10 px-2.5 py-1 text-xs font-semibold text-emerald-400 border border-emerald-500/20">
              Active in Production
            </span>
          </div>

          <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4 text-xs">
            <div>
              <span className="text-slate-400 uppercase font-semibold text-[10px]">Auto-Approve Cutoff</span>
              <p className="text-base font-bold text-emerald-400 mt-0.5">&lt; {policy.verify_threshold}</p>
            </div>
            <div>
              <span className="text-slate-400 uppercase font-semibold text-[10px]">Manual Review Band</span>
              <p className="text-base font-bold text-amber-400 mt-0.5">
                {policy.verify_threshold} – {policy.block_threshold}
              </p>
            </div>
            <div>
              <span className="text-slate-400 uppercase font-semibold text-[10px]">Direct Block Cutoff</span>
              <p className="text-base font-bold text-rose-400 mt-0.5">&ge; {policy.block_threshold}</p>
            </div>
            <div>
              <span className="text-slate-400 uppercase font-semibold text-[10px]">VIP Exemption</span>
              <p className="text-base font-bold text-white mt-0.5">
                {policy.vip_exemption_enabled ? "Enabled" : "Disabled"}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Interactive Simulation Sandbox */}
      <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 p-6 backdrop-blur-md">
        <h3 className="text-base font-bold text-white">Counterfactual Threshold Simulator</h3>
        <p className="text-xs text-slate-400 mt-1 mb-6">
          Adjust risk score boundaries to evaluate operational review workload and financial loss tradeoffs.
        </p>

        {/* Sliders Form */}
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 bg-slate-950/60 p-5 rounded-xl border border-slate-800 mb-6">
          <div className="space-y-2">
            <div className="flex justify-between text-xs">
              <label className="font-semibold text-slate-200">Manual Review Threshold (Verify)</label>
              <span className="font-mono font-bold text-amber-400">{verifyThreshold.toFixed(2)}</span>
            </div>
            <input
              type="range"
              min="0.10"
              max="0.60"
              step="0.05"
              value={verifyThreshold}
              onChange={(e) => setVerifyThreshold(parseFloat(e.target.value))}
              className="w-full accent-blue-500 cursor-pointer"
            />
            <p className="text-[11px] text-slate-500">
              Claims with calibrated probability below this score will be auto-approved immediately.
            </p>
          </div>

          <div className="space-y-2">
            <div className="flex justify-between text-xs">
              <label className="font-semibold text-slate-200">Automated Block Threshold</label>
              <span className="font-mono font-bold text-rose-400">{blockThreshold.toFixed(2)}</span>
            </div>
            <input
              type="range"
              min="0.65"
              max="0.95"
              step="0.05"
              value={blockThreshold}
              onChange={(e) => setBlockThreshold(parseFloat(e.target.value))}
              className="w-full accent-blue-500 cursor-pointer"
            />
            <p className="text-[11px] text-slate-500">
              Claims with calibrated probability above this score will be blocked automatically.
            </p>
          </div>
        </div>

        <button
          onClick={handleRunSimulation}
          disabled={simulating}
          className="rounded-lg bg-blue-600 px-5 py-2 text-xs font-semibold text-white shadow-md shadow-blue-500/20 transition hover:bg-blue-500 disabled:opacity-50"
        >
          {simulating ? "Simulating..." : "Run Counterfactual Simulation"}
        </button>

        {/* Simulation Output Cards */}
        {simulation && (
          <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-3 border-t border-slate-800 pt-6">
            <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">
              <span className="text-[10px] font-semibold uppercase text-slate-400">Review Queue Workload</span>
              <p
                className={`mt-1 text-2xl font-bold ${
                  simulation.review_queue_workload_change_percent <= 0 ? "text-emerald-400" : "text-rose-400"
                }`}
              >
                {simulation.review_queue_workload_change_percent > 0 ? "+" : ""}
                {simulation.review_queue_workload_change_percent}%
              </p>
              <p className="text-[11px] text-slate-500">Change in manual reviews</p>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">
              <span className="text-[10px] font-semibold uppercase text-slate-400">Simulated Expected Loss</span>
              <p className="mt-1 text-2xl font-bold text-amber-400">
                {formatCurrency(simulation.simulated_expected_loss)}
              </p>
              <p className="text-[11px] text-slate-500">Residual risk exposure</p>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">
              <span className="text-[10px] font-semibold uppercase text-slate-400">Simulated Allocation</span>
              <div className="mt-2 flex gap-3 text-xs font-medium">
                <span className="text-emerald-400">Appr: {simulation.simulated_distribution.APPROVE || 0}</span>
                <span className="text-amber-400">Rev: {simulation.simulated_distribution.VERIFY || 0}</span>
                <span className="text-rose-400">Blk: {simulation.simulated_distribution.BLOCK || 0}</span>
              </div>
              <p className="text-[11px] text-slate-500 mt-1">Cohort size: {simulation.cases_evaluated} cases</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
