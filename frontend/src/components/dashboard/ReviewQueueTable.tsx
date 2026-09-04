import React from "react";
import Link from "next/link";
import { ReviewQueueItem } from "../../lib/types";
import { formatCurrency, formatDate, getActionBadgeClass, getPriorityBadgeClass } from "../../lib/utils";

interface ReviewQueueTableProps {
  items: ReviewQueueItem[];
  loading?: boolean;
}

export function ReviewQueueTable({ items, loading }: ReviewQueueTableProps) {
  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center rounded-xl border border-slate-800 bg-slate-900/50 text-sm text-slate-400">
        Loading review queue...
      </div>
    );
  }

  if (!items || items.length === 0) {
    return (
      <div className="flex h-48 flex-col items-center justify-center rounded-xl border border-slate-800 bg-slate-900/50 text-sm text-slate-400">
        <span className="text-base font-medium text-slate-300">All clear!</span>
        <p className="mt-1 text-xs text-slate-500">No return requests pending manual review.</p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-slate-800/80 bg-slate-900/60 backdrop-blur-md">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-800 bg-slate-950/60 text-xs font-semibold uppercase tracking-wider text-slate-400">
            <tr>
              <th className="px-5 py-3.5">Risk Score</th>
              <th className="px-5 py-3.5">Priority</th>
              <th className="px-5 py-3.5">Return ID</th>
              <th className="px-5 py-3.5">Customer</th>
              <th className="px-5 py-3.5">Refund Amount</th>
              <th className="px-5 py-3.5">Primary Reason</th>
              <th className="px-5 py-3.5">Recommended</th>
              <th className="px-5 py-3.5">Status</th>
              <th className="px-5 py-3.5 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 text-slate-300">
            {items.map((item) => {
              const scorePct = (item.risk_score * 100).toFixed(1);
              const isHigh = item.risk_score >= 0.8;
              const isMid = item.risk_score >= 0.5 && item.risk_score < 0.8;

              return (
                <tr
                  key={item.request_id}
                  className="transition-colors hover:bg-slate-800/40"
                >
                  <td className="whitespace-nowrap px-5 py-4 font-mono">
                    <div className="flex items-center gap-2">
                      <div
                        className={`h-2.5 w-2.5 rounded-full ${
                          isHigh ? "bg-rose-500" : isMid ? "bg-amber-500" : "bg-emerald-500"
                        }`}
                      />
                      <span className="font-semibold text-white">{scorePct}%</span>
                    </div>
                  </td>
                  <td className="whitespace-nowrap px-5 py-4">
                    <span className={`rounded-md px-2 py-0.5 text-xs ${getPriorityBadgeClass(item.priority)}`}>
                      {item.priority}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-5 py-4 font-mono font-medium text-blue-400">
                    <Link href={`/cases/${item.request_id}`} className="hover:underline">
                      {item.request_id}
                    </Link>
                  </td>
                  <td className="whitespace-nowrap px-5 py-4 font-mono text-xs text-slate-400">
                    {item.user_id}
                  </td>
                  <td className="whitespace-nowrap px-5 py-4 font-semibold text-slate-100">
                    {formatCurrency(item.refund_amount)}
                  </td>
                  <td className="max-w-xs truncate px-5 py-4 text-xs text-slate-400" title={item.primary_reason || ""}>
                    {item.primary_reason || "Behavioral anomaly detected"}
                  </td>
                  <td className="whitespace-nowrap px-5 py-4">
                    <span className={`rounded-md px-2.5 py-1 text-xs font-semibold ${getActionBadgeClass(item.action)}`}>
                      {item.action}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-5 py-4 text-xs">
                    <span className="rounded-md bg-slate-800 px-2 py-0.5 text-slate-300">
                      {item.status}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-5 py-4 text-right">
                    <Link
                      href={`/cases/${item.request_id}`}
                      className="inline-flex items-center rounded-lg bg-blue-600/20 px-3 py-1.5 text-xs font-semibold text-blue-400 transition hover:bg-blue-600 hover:text-white"
                    >
                      Investigate →
                    </Link>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
