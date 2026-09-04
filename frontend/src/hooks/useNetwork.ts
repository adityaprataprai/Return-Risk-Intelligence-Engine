"use client";

import { useEffect, useState } from "react";
import { fetchNetworkGraph } from "../lib/api";
import { NetworkGraphResponse } from "../lib/types";

export function useNetwork(requestId: string) {
  const [network, setNetwork] = useState<NetworkGraphResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    async function load() {
      if (!requestId) return;
      try {
        setLoading(true);
        const res = await fetchNetworkGraph(requestId);
        if (mounted) {
          setNetwork(res);
          setError(null);
        }
      } catch (err: any) {
        if (mounted) setError(err.message || "Failed to load network graph");
      } finally {
        if (mounted) setLoading(false);
      }
    }
    load();
    return () => {
      mounted = false;
    };
  }, [requestId]);

  return { network, loading, error };
}
