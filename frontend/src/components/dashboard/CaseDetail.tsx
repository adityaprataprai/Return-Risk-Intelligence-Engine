"use client";

import React, { useState } from "react";
import { CaseDetail as CaseDetailType, NetworkGraphResponse, TimelineResponse } from "../../lib/types";
import { formatCurrency, formatDate, getActionBadgeClass } from "../../lib/utils";
import { ExplanationPanel } from "./ExplanationPanel";
import { NetworkGraph } from "./NetworkGraph";
import { Timeline } from "./Timeline";

interface CaseDetailProps {
  caseDetail: CaseDetailType;
  timeline?: TimelineResponse | null;
  network?: NetworkGraphResponse | null;
  onActionSubmit: (action: string, notes?: string, overrideReason?: string) => Promise<any>;
}

export function CaseDetail({ caseDetail, timeline, network, onActionSubmit }: CaseDetailProps) {
  const [activeTab, setActiveTab] = useState<"overview" | "explanation" | "timeline" | "network" | "economics" | "audit">("explanation");
  const [actionModalOpen, setActionModalOpen] = useState(false);
  const [selectedAction, setSelectedAction] = useState<string>("");
  const [overrideReason, setOverrideReason] = useState("");
  const [notes, setNotes] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const openActionDialog = (action: string) => {
    setSelectedAction(action);
    setOverrideReason("");
    setNotes("");
    setActionModalOpen(true);
  };

  const handleConfirmAction = async () => {
    setIsSubmitting(true);
    try {
      await onActionSubmit(selectedAction, notes, overrideReason);
      setActionModalOpen(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  const scorePct = (caseDetail.risk.risk_score * 100).toFixed(1);

  return (
    <div className="space-y-6">
      {/* Case Header Banner */}
      <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 p-6 backdrop-blur-md">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-xl font-bold font-mono text-white">{caseDetail.request_id}</h2>
              <span className={`rounded-md px-2.5 py-0.5 text-xs font-semibold ${getActionBadgeClass(caseDetail.risk.action)}`}>
                Recommended: {caseDetail.risk.action}
              </span>
              <span className="rounded-md bg-slate-800 px-2 py-0.5 text-xs text-slate-300">
                Status: {caseDetail.status}
              </span>
            </div>
            <p className="mt-1 text-xs text-slate-400">
              Claimant: <span className="font-mono text-slate-300">{caseDetail.user_id}</span> • Transaction:{" "}
              <span className="font-mono text-slate-300">{caseDetail.transaction_id}</span> • Initiated:{" "}
              {formatDate(caseDetail.created_at)}
            </p>
          </div>

          {/* Action Trigger Buttons */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => openActionDialog("APPROVE")}
              className="rounded-lg bg-emerald-600/20 px-4 py-2 text-xs font-semibold text-emerald-400 border border-emerald-500/30 transition hover:bg-emerald-600 hover:text-white"
            >
              ✓ Approve
            </button>
            <button
              onClick={() => openActionDialog("ESCALATE")}
              className="rounded-lg bg-amber-600/20 px-4 py-2 text-xs font-semibold text-amber-400 border border-amber-500/30 transition hover:bg-amber-600 hover:text-white"
            >
              ⚡ Escalate
            </button>
            <button
              onClick={() => openActionDialog("REJECT")}
              className="rounded-lg bg-rose-600/20 px-4 py-2 text-xs font-semibold text-rose-400 border border-rose-500/30 transition hover:bg-rose-600 hover:text-white"
            >
              ✕ Block Claim
            </button>
          </div>
        </div>

        {/* Quick KPI Bar */}
        <div className="mt-6 grid grid-cols-2 gap-4 border-t border-slate-800/80 pt-4 sm:grid-cols-4">
          <div>
            <span className="text-[10px] font-semibold uppercase text-slate-400">Calibrated Risk</span>
            <p className="text-lg font-bold text-rose-400">{scorePct}%</p>
          </div>
          <div>
            <span className="text-[10px] font-semibold uppercase text-slate-400">Refund Amount</span>
            <p className="text-lg font-bold text-white">{formatCurrency(caseDetail.order.refund_amount)}</p>
          </div>
          <div>
            <span className="text-[10px] font-semibold uppercase text-slate-400">Expected Loss</span>
            <p className="text-lg font-bold text-amber-400">{formatCurrency(caseDetail.risk.expected_loss)}</p>
          </div>
          <div>
            <span className="text-[10px] font-semibold uppercase text-slate-400">Model Lineage</span>
            <p className="text-xs font-mono text-slate-300 mt-1">{caseDetail.risk.model_version}</p>
          </div>
        </div>
      </div>

      {/* Tabs Navigation */}
      <div className="border-b border-slate-800">
        <nav className="flex gap-4">
          {[
            { id: "explanation", label: "TreeSHAP Explainability" },
            { id: "overview", label: "Case Context" },
            { id: "timeline", label: "Behavioral Timeline" },
            { id: "network", label: "Identity Network" },
            { id: "economics", label: "Financial Economics" },
            { id: "audit", label: "Analyst Audit Log" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`pb-3 text-xs font-semibold uppercase tracking-wider transition ${
                activeTab === tab.id
                  ? "border-b-2 border-blue-500 text-blue-400"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Contents */}
      <div className="pt-2">
        {activeTab === "explanation" && (
          <ExplanationPanel explanation={caseDetail.explanation} />
        )}

        {activeTab === "overview" && (
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
              <h4 className="text-sm font-semibold text-white mb-3">Order & Transaction Details</h4>
              <dl className="space-y-2 text-xs">
                <div className="flex justify-between py-1 border-b border-slate-800">
                  <dt className="text-slate-400">Transaction ID</dt>
                  <dd className="font-mono text-slate-200">{caseDetail.order.transaction_id}</dd>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-800">
                  <dt className="text-slate-400">Original Order Value</dt>
                  <dd className="font-semibold text-slate-100">{formatCurrency(caseDetail.order.order_amount)}</dd>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-800">
                  <dt className="text-slate-400">Requested Refund</dt>
                  <dd className="font-semibold text-rose-400">{formatCurrency(caseDetail.order.refund_amount)}</dd>
                </div>
                <div className="flex justify-between py-1">
                  <dt className="text-slate-400">Merchant Account</dt>
                  <dd className="font-mono text-slate-200">{caseDetail.merchant_id}</dd>
                </div>
              </dl>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
              <h4 className="text-sm font-semibold text-white mb-3">Customer Profile</h4>
              <dl className="space-y-2 text-xs">
                <div className="flex justify-between py-1 border-b border-slate-800">
                  <dt className="text-slate-400">Customer ID</dt>
                  <dd className="font-mono text-blue-400">{caseDetail.user_id}</dd>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-800">
                  <dt className="text-slate-400">Assigned Investigator</dt>
                  <dd className="text-slate-200">{caseDetail.assignee || "Unassigned"}</dd>
                </div>
                <div className="flex justify-between py-1">
                  <dt className="text-slate-400">Current Status</dt>
                  <dd className="text-slate-200">{caseDetail.status}</dd>
                </div>
              </dl>
            </div>
          </div>
        )}

        {activeTab === "timeline" && (
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6">
            <h4 className="text-sm font-semibold text-white mb-4">Customer Behavioral Event Timeline</h4>
            <Timeline events={timeline?.events || []} />
          </div>
        )}

        {activeTab === "network" && (
          <NetworkGraph data={network || null} />
        )}

        {activeTab === "economics" && (
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
            <h4 className="text-sm font-semibold text-white mb-3">Unit Economics & Loss Mitigation</h4>
            <div className="space-y-3 text-xs">
              <div className="flex justify-between p-3 rounded bg-slate-950/60 border border-slate-800">
                <span className="text-slate-300">Requested Refund Amount</span>
                <span className="font-semibold text-white">{formatCurrency(caseDetail.order.refund_amount)}</span>
              </div>
              <div className="flex justify-between p-3 rounded bg-slate-950/60 border border-slate-800">
                <span className="text-slate-300">Expected Financial Loss (Risk × Value)</span>
                <span className="font-semibold text-amber-400">{formatCurrency(caseDetail.risk.expected_loss)}</span>
              </div>
              <div className="flex justify-between p-3 rounded bg-slate-950/60 border border-slate-800">
                <span className="text-slate-300">Estimated Return Shipping & Handling Cost</span>
                <span className="font-semibold text-slate-300">{formatCurrency(450.0)}</span>
              </div>
            </div>
          </div>
        )}

        {activeTab === "audit" && (
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
            <h4 className="text-sm font-semibold text-white mb-3">Prior Investigator Actions</h4>
            {caseDetail.analyst_actions && caseDetail.analyst_actions.length > 0 ? (
              <div className="space-y-3">
                {caseDetail.analyst_actions.map((act) => (
                  <div key={act.action_id} className="rounded-lg border border-slate-800 bg-slate-950 p-4 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-blue-400">{act.analyst_id} applied {act.action}</span>
                      <span className="text-slate-400 font-mono">{formatDate(act.created_at)}</span>
                    </div>
                    {act.override_reason && (
                      <p className="mt-2 text-slate-300 font-medium">
                        Justification: &ldquo;{act.override_reason}&rdquo;
                      </p>
                    )}
                    {act.notes && (
                      <p className="mt-1 text-slate-400">
                        Notes: {act.notes}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-400">No manual investigator decisions logged yet.</p>
            )}
          </div>
        )}
      </div>

      {/* Manual Review Modal Dialog */}
      {actionModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-xl border border-slate-800 bg-slate-900 p-6 shadow-2xl">
            <h3 className="text-base font-bold text-white">Execute Action: {selectedAction}</h3>
            <p className="mt-1 text-xs text-slate-400">
              Submit your manual fraud investigation decision for {caseDetail.request_id}.
            </p>

            <div className="mt-4 space-y-4 text-xs">
              <div>
                <label className="font-semibold text-slate-300">Override Reason / Justification</label>
                <input
                  type="text"
                  value={overrideReason}
                  onChange={(e) => setOverrideReason(e.target.value)}
                  placeholder="e.g., Physical return inspection confirmed wardrobing"
                  className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-slate-200 outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="font-semibold text-slate-300">Investigative Notes</label>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Enter detailed observation notes for compliance audit..."
                  rows={3}
                  className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-slate-200 outline-none focus:border-blue-500"
                />
              </div>
            </div>

            <div className="mt-6 flex justify-end gap-3">
              <button
                onClick={() => setActionModalOpen(false)}
                disabled={isSubmitting}
                className="rounded-lg border border-slate-800 px-4 py-2 text-xs font-semibold text-slate-300 hover:bg-slate-800"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmAction}
                disabled={isSubmitting}
                className="rounded-lg bg-blue-600 px-4 py-2 text-xs font-semibold text-white hover:bg-blue-500 disabled:opacity-50"
              >
                {isSubmitting ? "Submitting..." : "Confirm Decision"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
