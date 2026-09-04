import React from "react";
import { RiskDistribution } from "../../lib/types";

interface RiskOverviewProps {
  distribution: RiskDistribution | null;
}

export function RiskOverview({ distribution }: RiskOverviewProps) {
  if (!distribution) {
    return (
      <div className="flex h-64 items-center justify-center rounded-xl border border-slate-800 bg-slate-900/50 text-sm text-slate-400">
        Loading risk distribution...
      </div>
    );
  }

  const maxCount = Math.max(...distribution.buckets.map((b) => b.count), 1);
  const totalDecisions =
    (distribution.decision_breakdown.APPROVE || 0) +
    (distribution.decision_breakdown.VERIFY || 0) +
    (distribution.decision_breakdown.BLOCK || 0) || 1;

  const apprPct = (((distribution.decision_breakdown.APPROVE || 0) / totalDecisions) * 100).toFixed(1);
  const revPct = (((distribution.decision_breakdown.VERIFY || 0) / totalDecisions) * 100).toFixed(1);
  const blkPct = (((distribution.decision_breakdown.BLOCK || 0) / totalDecisions) * 100).toFixed(1);

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
      {/* 10-Bucket Probability Histogram */}
      <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 p-6 backdrop-blur-md lg:col-span-2">
        <div className="flex items-center justify-between pb-4">
          <div>
            <h3 className="text-base font-semibold text-white">Risk Score Distribution (Deciles)</h3>
            <p className="text-xs text-slate-400">Distribution of evaluated claims across 0.0 - 1.0 probability bands</p>
          </div>
          <div className="rounded-md bg-slate-800 px-2.5 py-1 text-xs text-slate-300">
            Avg: <span className="font-semibold text-blue-400">{distribution.average_risk_score.toFixed(3)}</span>
          </div>
        </div>

        <div className="mt-4 flex h-48 items-end gap-2 pt-6">
          {distribution.buckets.map((b, idx) => {
            const heightPct = Math.max((b.count / maxCount) * 100, 4);
            const isHighRisk = idx >= 8;
            const isMidRisk = idx >= 4 && idx < 8;

            const barColor = isHighRisk
              ? "bg-rose-500 hover:bg-rose-400"
              : isMidRisk
              ? "bg-amber-500 hover:bg-amber-400"
              : "bg-emerald-500 hover:bg-emerald-400";

            return (
              <div key={b.range} className="group relative flex flex-1 flex-col items-center h-full justify-end">
                {/* Tooltip */}
                <div className="absolute -top-10 hidden rounded bg-slate-950 px-2 py-1 text-[10px] text-slate-200 shadow group-hover:block z-10 whitespace-nowrap border border-slate-800">
                  {b.range}: {b.count.toLocaleString()} ({b.percentage}%)
                </div>
                <div
                  style={{ height: `${heightPct}%` }}
                  className={`w-full rounded-t transition-all duration-300 ${barColor}`}
                />
                <span className="mt-2 text-[9px] text-slate-400">{b.range.split("-")[0]}</span>
              </div>
            );
          })}
        </div>
        <div className="mt-2 text-center text-[10px] text-slate-400">Probability Score (Low Risk → Severe Risk)</div>
      </div>

      {/* Decision Split Breakdown */}
      <div className="flex flex-col justify-between rounded-xl border border-slate-800/80 bg-slate-900/60 p-6 backdrop-blur-md">
        <div>
          <h3 className="text-base font-semibold text-white">Action Breakdown</h3>
          <p className="text-xs text-slate-400">Automated policy decision allocation</p>
        </div>

        <div className="my-6 space-y-4">
          <div>
            <div className="flex justify-between text-xs font-medium">
              <span className="text-emerald-400">APPROVE ({apprPct}%)</span>
              <span className="text-slate-300">{distribution.decision_breakdown.APPROVE?.toLocaleString() || 0}</span>
            </div>
            <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-slate-800">
              <div style={{ width: `${apprPct}%` }} className="h-full bg-emerald-500 rounded-full" />
            </div>
          </div>

          <div>
            <div className="flex justify-between text-xs font-medium">
              <span className="text-amber-400">VERIFY ({revPct}%)</span>
              <span className="text-slate-300">{distribution.decision_breakdown.VERIFY?.toLocaleString() || 0}</span>
            </div>
            <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-slate-800">
              <div style={{ width: `${revPct}%` }} className="h-full bg-amber-500 rounded-full" />
            </div>
          </div>

          <div>
            <div className="flex justify-between text-xs font-medium">
              <span className="text-rose-400">BLOCK ({blkPct}%)</span>
              <span className="text-slate-300">{distribution.decision_breakdown.BLOCK?.toLocaleString() || 0}</span>
            </div>
            <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-slate-800">
              <div style={{ width: `${blkPct}%` }} className="h-full bg-rose-500 rounded-full" />
            </div>
          </div>
        </div>

        <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3 text-xs text-slate-400">
          ⚡ <strong>Policy Status</strong>: Auto-approval handles {apprPct}% of claims instantaneously without human intervention.
        </div>
      </div>
    </div>
  );
}
