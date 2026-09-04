"use client";

import React, { useEffect, useState } from "react";
import { fetchFinancialImpact, fetchFraudAnalytics } from "../../lib/api";
import { FinancialImpactResponse, FraudAnalyticsResponse } from "../../lib/types";
import { formatCurrency } from "../../lib/utils";

export default function AnalyticsPage() {
  const [fraudData, setFraudData] = useState<FraudAnalyticsResponse | null>(null);
  const [financeData, setFinanceData] = useState<FinancialImpactResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    async function load() {
      try {
        const [f, fi] = await Promise.all([
          fetchFraudAnalytics(),
          fetchFinancialImpact(),
        ]);
        if (mounted) {
          setFraudData(f);
          setFinanceData(fi);
        }
      } catch (e) {
        console.error("Analytics load error:", e);
      } finally {
        if (mounted) setLoading(false);
      }
    }
    load();
    return () => {
      mounted = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center rounded-xl border border-slate-800 bg-slate-900/50 text-sm text-slate-400">
        Loading fraud analytics and financial ROI models...
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">Fraud Typology & Financial ROI</h1>
        <p className="text-xs text-slate-400 mt-1">
          Detailed breakdown of return fraud vectors, financial loss mitigation, and operational return on investment.
        </p>
      </div>

      {/* Financial ROI Highlights */}
      {financeData && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 p-5 backdrop-blur-md">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Gross Merchandise Value</span>
            <p className="mt-2 text-2xl font-bold text-white">{formatCurrency(financeData.gross_merchandise_value)}</p>
            <p className="mt-1 text-xs text-slate-500">Total volume evaluated</p>
          </div>
          <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 p-5 backdrop-blur-md">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Fraud Loss Prevented</span>
            <p className="mt-2 text-2xl font-bold text-rose-400">{formatCurrency(financeData.fraud_loss_prevented)}</p>
            <p className="mt-1 text-xs text-slate-500">Direct blocked fraud claims</p>
          </div>
          <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 p-5 backdrop-blur-md">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Logistics Cost Saved</span>
            <p className="mt-2 text-2xl font-bold text-emerald-400">
              {formatCurrency(financeData.return_shipping_saved + financeData.handling_costs_preserved)}
            </p>
            <p className="mt-1 text-xs text-slate-500">Shipping & restocking preserved</p>
          </div>
          <div className="rounded-xl border border-blue-500/20 bg-blue-950/30 p-5 backdrop-blur-md">
            <span className="text-xs font-semibold uppercase tracking-wider text-blue-400">Net Engine ROI</span>
            <p className="mt-2 text-3xl font-extrabold text-blue-300">{financeData.roi_multiple}x</p>
            <p className="mt-1 text-xs text-blue-200/70">ROI on risk infrastructure</p>
          </div>
        </div>
      )}

      {/* Fraud Vectors Breakdown */}
      {fraudData && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Typology Mix */}
          <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 p-6 backdrop-blur-md">
            <h3 className="text-base font-semibold text-white mb-1">Abuse Typology Breakdown</h3>
            <p className="text-xs text-slate-400 mb-6">Distribution of detected fraud by behavioral attack vector</p>

            <div className="space-y-4">
              {fraudData.vectors.map((vec) => (
                <div key={vec.vector} className="space-y-1">
                  <div className="flex justify-between text-xs font-medium">
                    <span className="text-slate-200">{vec.title}</span>
                    <span className="text-slate-400 font-mono">
                      {vec.count} cases ({vec.percentage}%) • {formatCurrency(vec.amount)}
                    </span>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-slate-800">
                    <div
                      style={{ width: `${vec.percentage}%` }}
                      className="h-full rounded-full bg-blue-500 transition-all duration-500"
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* 7-Day Volume Trend */}
          <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 p-6 backdrop-blur-md">
            <h3 className="text-base font-semibold text-white mb-1">7-Day Volume & Flagged Trajectory</h3>
            <p className="text-xs text-slate-400 mb-6">Legitimate transactions vs detected abuse claims</p>

            <div className="flex h-52 items-end gap-3 pt-6">
              {fraudData.trend_daily.map((day) => {
                const total = day.legitimate_returns + day.flagged_fraud;
                const legitHeight = (day.legitimate_returns / 500) * 100;
                const fraudHeight = (day.flagged_fraud / 500) * 100;

                return (
                  <div key={day.date} className="group relative flex flex-1 flex-col items-center h-full justify-end">
                    <div className="absolute -top-12 hidden rounded bg-slate-950 px-2 py-1 text-[10px] text-slate-200 border border-slate-800 shadow z-10 whitespace-nowrap group-hover:block">
                      {day.date}: {day.flagged_fraud} flagged / {total} total
                    </div>
                    {/* Stacked Bar */}
                    <div
                      style={{ height: `${fraudHeight}%` }}
                      className="w-full bg-rose-500 rounded-t transition-all hover:bg-rose-400"
                    />
                    <div
                      style={{ height: `${legitHeight}%` }}
                      className="w-full bg-blue-600/70 transition-all hover:bg-blue-500"
                    />
                    <span className="mt-2 text-[10px] text-slate-400">{day.date}</span>
                  </div>
                );
              })}
            </div>

            <div className="mt-4 flex justify-center gap-6 text-[11px] text-slate-400 border-t border-slate-800 pt-3">
              <div className="flex items-center gap-2">
                <div className="h-2.5 w-2.5 rounded-sm bg-blue-600" />
                <span>Legitimate Returns</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="h-2.5 w-2.5 rounded-sm bg-rose-500" />
                <span>Blocked / Verified Fraud</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
