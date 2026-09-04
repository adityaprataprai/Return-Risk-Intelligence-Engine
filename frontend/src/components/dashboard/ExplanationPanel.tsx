import React from "react";
import { ExplanationRecord } from "../../lib/types";

interface ExplanationPanelProps {
  explanation: ExplanationRecord | null;
}

export function ExplanationPanel({ explanation }: ExplanationPanelProps) {
  if (!explanation) {
    return (
      <div className="flex h-48 items-center justify-center rounded-xl border border-slate-800 bg-slate-900/50 text-sm text-slate-400">
        No TreeSHAP explanation generated yet (status: PENDING).
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Overview Metrics Banner */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4">
          <span className="text-xs text-slate-400 uppercase font-semibold">Tree Explainer Baseline</span>
          <div className="mt-1 text-xl font-bold font-mono text-slate-200">
            {explanation.base_value?.toFixed(4) || "-4.6865"}
          </div>
          <p className="text-[11px] text-slate-500">Global expected log-odds</p>
        </div>
        <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4">
          <span className="text-xs text-slate-400 uppercase font-semibold">Raw Margin Score</span>
          <div className="mt-1 text-xl font-bold font-mono text-blue-400">
            {explanation.raw_margin?.toFixed(4) || "0.0000"}
          </div>
          <p className="text-[11px] text-slate-500">Uncalibrated booster output</p>
        </div>
        <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4">
          <span className="text-xs text-slate-400 uppercase font-semibold">Calibrated Risk</span>
          <div className="mt-1 text-xl font-bold font-mono text-rose-400">
            {((explanation.calibrated_probability || 0) * 100).toFixed(1)}%
          </div>
          <p className="text-[11px] text-slate-500">Isotonic calibrated probability</p>
        </div>
      </div>

      {/* Deterministic Reason Codes & Concrete Evidence */}
      <div>
        <h4 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
          Deterministic Reason Codes & Concrete Evidence
        </h4>
        <p className="text-xs text-slate-400 mb-3">
          Top risk-increasing features mapped to auditable narratives.
        </p>

        <div className="space-y-3">
          {explanation.reason_codes && explanation.reason_codes.length > 0 ? (
            explanation.reason_codes.map((rc) => (
              <div
                key={rc.code}
                className="rounded-xl border border-slate-800 bg-slate-950/70 p-4 transition hover:border-slate-700"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="rounded bg-rose-500/15 px-2 py-0.5 text-xs font-mono font-bold text-rose-400 border border-rose-500/30">
                      {rc.code}
                    </span>
                    <span className="text-sm font-semibold text-white">{rc.title}</span>
                  </div>
                  <span className="rounded bg-slate-800 px-2 py-0.5 text-[10px] text-slate-400 uppercase">
                    {rc.group}
                  </span>
                </div>
                <p className="mt-2.5 text-xs font-medium text-slate-200">
                  💬 &ldquo;{rc.evidence_text}&rdquo;
                </p>
              </div>
            ))
          ) : (
            <div className="p-4 rounded-xl border border-slate-800 text-xs text-slate-400">
              No elevated risk factors detected. Transaction meets baseline safety criteria.
            </div>
          )}
        </div>
      </div>

      {/* Semantic Domain Attributions */}
      {explanation.group_attributions && (
        <div>
          <h4 className="text-sm font-semibold uppercase tracking-wider text-slate-300 mb-3">
            Semantic Domain Attributions
          </h4>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {explanation.group_attributions.map((g) => {
              const isRisk = g.total_shap > 0;
              return (
                <div key={g.group_name} className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-slate-200">{g.display_name}</span>
                    <span
                      className={`font-mono font-bold ${
                        isRisk ? "text-rose-400" : "text-emerald-400"
                      }`}
                    >
                      {g.total_shap > 0 ? "+" : ""}
                      {g.total_shap.toFixed(3)}
                    </span>
                  </div>
                  <p className="mt-1 text-[11px] text-slate-400 line-clamp-2">{g.description}</p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Fair Lending & Data Confidence Guarantee */}
      {explanation.data_confidence && (
        <div className="rounded-xl border border-blue-500/20 bg-blue-950/20 p-4">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-blue-400">🛡️ Fair-Lending Data Confidence Assessment</span>
            <span className="rounded bg-blue-500/20 px-2 py-0.5 text-[10px] font-bold text-blue-300">
              {explanation.data_confidence.confidence_level}
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-300">
            {explanation.data_confidence.history_summary}
          </p>
          <div className="mt-2 text-[11px] text-slate-400">
            <strong>Non-Punitive Rule</strong>: Account tenure and cold-start indicators strictly evaluate data density and are never mapped to adverse fraud reason codes.
          </div>
        </div>
      )}
    </div>
  );
}
