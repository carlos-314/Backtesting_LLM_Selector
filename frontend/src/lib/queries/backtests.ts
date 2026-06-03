/**
 * Hooks de datos del contexto Backtesting (F3 §6.2, §6.5).
 *
 * Polling de `useBacktestQuery` cuando `enablePolling=true`: cadencia 2.5s,
 * pausa en background, parada en estado terminal (F3 §6.5).
 */
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import type { ApiError } from "@/lib/api-error";
import { queryKeys } from "@/lib/query-keys";

export type BacktestStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export interface BacktestSummary {
  id: string;
  name: string;
  status: BacktestStatus;
  created_by: string;
  created_at: string;
  completed_at: string | null;
}

export interface BacktestDetail {
  id: string;
  name: string;
  status: BacktestStatus;
  created_by: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  period: { start: string; end: string };
  initial_capital: string;
  base_currency: string;
  strategy_code: string;
  benchmark_code: string;
  weeks_total: number | null;
  weeks_processed: number | null;
  progress: { weeks_total: number; weeks_processed: number } | null;
  error: { code: string; message: string } | null;
}

export interface BacktestResult {
  metrics: {
    total_return: string | null;
    cagr: string | null;
    volatility: string | null;
    sharpe: string | null;
    max_drawdown: string | null;
  };
  equity_curve: { series: "portfolio" | "benchmark"; date: string; value: string }[];
  snapshot_summary: {
    weeks: number;
    first_week: string | null;
    last_week: string | null;
  };
}

const TERMINAL: Set<BacktestStatus> = new Set(["completed", "failed", "cancelled"]);

export function useBacktestsListQuery(params: {
  status?: string;
  cursor?: string | null;
} = {}) {
  return useQuery<
    { items: BacktestSummary[]; next_cursor: string | null },
    ApiError
  >({
    queryKey: queryKeys.backtests.list({ status: params.status, cursor: params.cursor ?? null }),
    queryFn: () =>
      apiFetch("/api/v1/backtests", {
        query: { status: params.status, cursor: params.cursor ?? undefined, limit: 50 },
      }),
  });
}

export function useBacktestQuery(id: string | undefined, opts: { polling?: boolean } = {}) {
  return useQuery<BacktestDetail, ApiError>({
    queryKey: queryKeys.backtests.detail(id ?? ""),
    queryFn: () => apiFetch(`/api/v1/backtests/${id}`),
    enabled: !!id,
    refetchInterval: (query) => {
      if (!opts.polling) return false;
      const status = (query.state.data as BacktestDetail | undefined)?.status;
      if (status && TERMINAL.has(status)) return false;
      return 2500;
    },
    // F3 §6.5: pausa el polling cuando la pestaña no está visible
    refetchIntervalInBackground: false,
  });
}

export function useBacktestResultQuery(id: string | undefined, enabled = true) {
  return useQuery<BacktestResult, ApiError>({
    queryKey: queryKeys.backtests.result(id ?? ""),
    queryFn: () => apiFetch(`/api/v1/backtests/${id}/result`),
    enabled: !!id && enabled,
  });
}

export interface CreateBacktestBody {
  name: string;
  period_start?: string;
  period_end?: string;
  initial_capital?: string;
  base_currency?: string;
  strategy_code?: string;
  benchmark_code?: string;
}

export function useCreateBacktestMutation() {
  const qc = useQueryClient();
  return useMutation<BacktestDetail, ApiError, CreateBacktestBody>({
    mutationFn: (body) =>
      apiFetch("/api/v1/backtests", { method: "POST", body }),
    // F3 §6.4: las mutaciones invalidan, no parchean
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.backtests.all() });
    },
  });
}

export function useCancelBacktestMutation() {
  const qc = useQueryClient();
  return useMutation<BacktestDetail, ApiError, string>({
    mutationFn: (id) =>
      apiFetch(`/api/v1/backtests/${id}/cancel`, { method: "POST" }),
    onSuccess: (_data, id) => {
      void qc.invalidateQueries({ queryKey: queryKeys.backtests.detail(id) });
      void qc.invalidateQueries({ queryKey: queryKeys.backtests.list() });
    },
  });
}
