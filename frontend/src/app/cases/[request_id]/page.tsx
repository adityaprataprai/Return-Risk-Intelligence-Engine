"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { CaseDetail } from "../../../components/dashboard/CaseDetail";
import { useCaseDetail } from "../../../hooks/useCases";
import { fetchCaseTimeline, fetchNetworkGraph } from "../../../lib/api";
import { NetworkGraphResponse, TimelineResponse } from "../../../lib/types";

export default function CaseDetailPage() {
  const params = useParams();
  const requestId = Array.isArray(params?.request_id) ? params.request_id[0] : (params?.request_id as string) || "";

  const { caseDetail, loading, takeAction } = useCaseDetail(requestId);
  const [timeline, setTimeline] = useState<TimelineResponse | null>(null);
  const [network, setNetwork] = useState<NetworkGraphResponse | null>(null);

  useEffect(() => {
    let mounted = true;
    async function loadAux() {
      if (!requestId) return;
      try {
        const [tl, net] = await Promise.all([
          fetchCaseTimeline(requestId),
          fetchNetworkGraph(requestId),
        ]);
        if (mounted) {
          setTimeline(tl);
          setNetwork(net);
        }
      } catch (e) {
        console.error("Auxiliary data load error:", e);
      }
    }
    loadAux();
    return () => {
      mounted = false;
    };
  }, [requestId]);

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center rounded-xl border border-slate-800 bg-slate-900/50 text-sm text-slate-400">
        Loading case investigation workbench for {requestId}...
      </div>
    );
  }

  if (!caseDetail) {
    return (
      <div className="flex h-96 flex-col items-center justify-center rounded-xl border border-slate-800 bg-slate-900/50 text-sm text-slate-400">
        <span className="text-base font-medium text-slate-300">Case Not Found</span>
        <p className="mt-1 text-xs text-slate-500">Could not find records for request ID &apos;{requestId}&apos;.</p>
        <Link href="/review-queue" className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-xs font-semibold text-white">
          ← Back to Review Queue
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumbs */}
      <div className="flex items-center gap-2 text-xs text-slate-400">
        <Link href="/review-queue" className="hover:text-blue-400 transition">
          ← Review Queue
        </Link>
        <span>/</span>
        <span className="font-mono text-slate-200">{requestId}</span>
      </div>

      <CaseDetail
        caseDetail={caseDetail}
        timeline={timeline}
        network={network}
        onActionSubmit={takeAction}
      />
    </div>
  );
}
