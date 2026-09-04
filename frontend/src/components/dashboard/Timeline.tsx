import React from "react";
import { TimelineEvent } from "../../lib/types";
import { formatCurrency, formatDate } from "../../lib/utils";

interface TimelineProps {
  events: TimelineEvent[];
}

export function Timeline({ events }: TimelineProps) {
  if (!events || events.length === 0) {
    return (
      <div className="flex h-40 items-center justify-center rounded-xl border border-slate-800 bg-slate-900/50 text-xs text-slate-400">
        No prior behavioral events recorded.
      </div>
    );
  }

  return (
    <div className="relative pl-6 before:absolute before:bottom-0 before:left-2.5 before:top-2 before:w-0.5 before:bg-slate-800">
      <div className="space-y-6">
        {events.map((evt) => {
          let dotColor = "bg-blue-500 border-blue-400";
          if (evt.badge_type === "danger") dotColor = "bg-rose-500 border-rose-400";
          if (evt.badge_type === "warning") dotColor = "bg-amber-500 border-amber-400";
          if (evt.badge_type === "success") dotColor = "bg-emerald-500 border-emerald-400";

          return (
            <div key={evt.event_id} className="relative group">
              {/* Dot */}
              <div
                className={`absolute -left-6 top-1.5 h-3 w-3 -translate-x-1/2 rounded-full border-2 border-slate-950 ${dotColor}`}
              />

              <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 p-4 backdrop-blur-sm transition hover:border-slate-700">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-white">{evt.title}</span>
                  <span className="text-[11px] font-mono text-slate-400">{formatDate(evt.timestamp)}</span>
                </div>
                <p className="mt-1 text-xs text-slate-300">{evt.description}</p>
                {evt.amount && (
                  <div className="mt-2 text-xs font-semibold text-slate-100">
                    Amount: {formatCurrency(evt.amount)}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
