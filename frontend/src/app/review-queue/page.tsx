"use client";

import React, { useState } from "react";
import { ReviewQueueTable } from "../../components/dashboard/ReviewQueueTable";
import { useReviewQueue } from "../../hooks/useCases";

export default function ReviewQueuePage() {
  const [statusFilter, setStatusFilter] = useState("PENDING_REVIEW");
  const [search, setSearch] = useState("");
  const { data, loading, reload } = useReviewQueue(statusFilter, search);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Analyst Review Queue</h1>
          <p className="text-xs text-slate-400 mt-1">
            Prioritized case queue for borderline and elevated return abuse claims.
          </p>
        </div>

        <button
          onClick={reload}
          className="self-start rounded-lg border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs font-semibold text-slate-300 transition hover:bg-slate-800"
        >
          ↻ Refresh
        </button>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col gap-4 rounded-xl border border-slate-800/80 bg-slate-900/60 p-4 sm:flex-row sm:items-center sm:justify-between">
        {/* Status Tabs */}
        <div className="flex gap-1.5 rounded-lg bg-slate-950 p-1 border border-slate-800 text-xs">
          {[
            { id: "PENDING_REVIEW", label: "Open Queue" },
            { id: "ALL", label: "All Cases" },
            { id: "RESOLVED", label: "Resolved" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setStatusFilter(tab.id)}
              className={`rounded-md px-3 py-1.5 font-semibold transition ${
                statusFilter === tab.id
                  ? "bg-blue-600 text-white shadow-sm"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Search Input */}
        <div className="w-full sm:w-72">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search return ID, user ID..."
            className="w-full rounded-lg border border-slate-800 bg-slate-950 px-3.5 py-1.5 text-xs text-slate-200 outline-none focus:border-blue-500"
          />
        </div>
      </div>

      {/* Cases Table */}
      <ReviewQueueTable items={data?.items || []} loading={loading} />
    </div>
  );
}
