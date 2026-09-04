"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchOverviewKPIs, fetchRiskDistribution } from "../lib/api";
import { OverviewKPIs, RiskDistribution } from "../lib/types";

export function useOverview() {
  const [kpis, setKpis] = useState<OverviewKPIs | null>(null);
  const [distribution, setDistribution] = useState<RiskDistribution | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async (showLoading = false) => {
    try {
      if (showLoading) setLoading(true);
      const [kpiData, distData] = await Promise.all([
        fetchOverviewKPIs(),
        fetchRiskDistribution(),
      ]);
      setKpis(kpiData);
      setDistribution(distData);
      setError(null);
    } catch (err: any) {
      setError(err.message || "Failed to load overview data");
    } finally {
      if (showLoading) setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Initial fetch
    loadData(true);

    // Auto-refresh when user refocuses window
    const handleFocus = () => loadData(false);
    window.addEventListener("focus", handleFocus);

    // Background polling interval every 5 seconds to keep KPIs in real-time sync
    const intervalId = setInterval(() => {
      loadData(false);
    }, 5000);

    return () => {
      window.removeEventListener("focus", handleFocus);
      clearInterval(intervalId);
    };
  }, [loadData]);

  return { kpis, distribution, loading, error, refresh: () => loadData(true) };
}
