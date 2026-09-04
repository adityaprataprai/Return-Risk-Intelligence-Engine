"use client";

import React from "react";
import Link from "next/link";
import { KpiCard } from "../../components/dashboard/KpiCard";
import { RiskOverview } from "../../components/dashboard/RiskOverview";
import { useOverview } from "../../hooks/useOverview";
import { formatCurrency, formatPercent } from "../../lib/utils";

export default function OverviewPage() {
  const { kpis, distribution, loading } = useOverview();

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">Executive Risk Overview</h1>
        <p className="text-xs text-slate-400 mt-1">
          Real-time return abuse metrics, automated decision distribution, and financial loss mitigation.
        </p>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          title="Total Claims Evaluated"
          value={kpis ? kpis.total_cases_evaluated.toLocaleString() : "..."}
          subtitle={`Avg scoring latency: ${kpis ? kpis.avg_decision_latency_ms : 10.5}ms`}
          trend={{ value: "+12.4% vs last week", isPositive: true }}
        />
        <KpiCard
          title="Prevented Fraud Loss"
          value={kpis ? formatCurrency(kpis.loss_prevented_amount) : "..."}
          subtitle="Direct blocked abuse claims"
          trend={{ value: "+8.6% saved", isPositive: true }}
        />
        <KpiCard
          title="Auto-Approval Rate"
          value={kpis ? formatPercent(kpis.approval_rate) : "..."}
          subtitle="Instant frictionless refunds"
          trend={{ value: "SLA: > 75%", isPositive: true }}
        />
        <KpiCard
          title="Pending Review Queue"
          value={kpis ? kpis.active_review_queue_count.toString() : "..."}
          subtitle="High-priority suspect cases"
          trend={{ value: "Avg turnaround: 18m", isPositive: true }}
        />
      </div>

      {/* Risk Distribution & Actions */}
      <RiskOverview distribution={distribution} />

      {/* Quick Access Action Bar */}
      <div className="flex items-center justify-between rounded-xl border border-slate-800/80 bg-slate-900/60 p-5 backdrop-blur-md">
        <div>
          <h4 className="text-sm font-semibold text-white">Need to triage open suspect claims?</h4>
          <p className="text-xs text-slate-400 mt-0.5">
            There are currently {kpis?.active_review_queue_count || 20} returns routed to manual investigator queues.
          </p>
        </div>
        <Link
          href="/review-queue"
          className="rounded-lg bg-blue-600 px-4 py-2 text-xs font-semibold text-white transition hover:bg-blue-500 shadow-md shadow-blue-500/20"
        >
          Open Review Queue →
        </Link>
      </div>
    </div>
  );
}
