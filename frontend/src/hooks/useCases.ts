"use client";

import { useEffect, useState } from "react";
import { fetchCaseDetail, fetchReviewQueue, submitCaseAction } from "../lib/api";
import { CaseDetail, ReviewQueueResponse } from "../lib/types";

export function useReviewQueue(status: string = "PENDING_REVIEW", search?: string) {
  const [data, setData] = useState<ReviewQueueResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const reload = async () => {
    try {
      setLoading(true);
      const res = await fetchReviewQueue(status, 50, 0, search);
      setData(res);
      setError(null);
    } catch (err: any) {
      setError(err.message || "Failed to load review queue");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    reload();
  }, [status, search]);

  return { data, loading, error, reload };
}

export function useCaseDetail(requestId: string) {
  const [caseDetail, setCaseDetail] = useState<CaseDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const reload = async () => {
    if (!requestId) return;
    try {
      setLoading(true);
      const res = await fetchCaseDetail(requestId);
      setCaseDetail(res);
      setError(null);
    } catch (err: any) {
      setError(err.message || "Failed to load case detail");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    reload();
  }, [requestId]);

  const takeAction = async (action: string, notes?: string, overrideReason?: string) => {
    const res = await submitCaseAction(requestId, {
      action,
      analyst_id: "analyst_me",
      override_reason: overrideReason,
      notes,
    });
    if (res.success) {
      await reload();
    }
    return res;
  };

  return { caseDetail, loading, error, reload, takeAction };
}
