/**
 * Hooks de datos del contexto Screening (F3 §6.2).
 *
 * Todas las llamadas pasan por `apiFetch`; el bearer se cablea solo.
 */
import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import type { ApiError } from "@/lib/api-error";
import { queryKeys } from "@/lib/query-keys";

export interface WeekSummary {
  week_date: string;
  run_code: string;
  resolved_run_id: number;
  pick_count: number;
}

export interface MatrixResponse {
  weeks: { week_date: string; run_code: string; resolved_run_id: number }[];
  companies: {
    ticker: string;
    name: string | null;
    country: string | null;
    currency: string | null;
    exchange: string | null;
  }[];
  cells: {
    ticker: string;
    week_date: string;
    state: "selected" | "in_universe";
  }[];
}

export interface PickResponse {
  ticker: string;
  role: string | null;
  name: string | null;
}

export interface CompanyListItem {
  ticker: string;
  name: string | null;
  country: string | null;
  exchange: string | null;
  currency: string | null;
  in_portfolio: boolean;
}

export interface CompanyDetail {
  ticker: string;
  week_date: string;
  run_code: string;
  name: string | null;
  country: string | null;
  exchange: string | null;
  currency: string | null;
  in_portfolio: boolean;
  raw_processed_stock: Record<string, unknown> | null;
}

export function useWeeksQuery(params: { from?: string; to?: string } = {}) {
  return useQuery<{ items: WeekSummary[] }, ApiError>({
    queryKey: queryKeys.screening.weeks(params),
    queryFn: () =>
      apiFetch("/api/v1/weeks", { query: { from: params.from, to: params.to } }),
  });
}

export function useMatrixQuery(params: { from: string; to: string }) {
  return useQuery<MatrixResponse, ApiError>({
    queryKey: queryKeys.screening.matrix(params.from, params.to),
    queryFn: () =>
      apiFetch("/api/v1/screening/matrix", {
        query: { from: params.from, to: params.to },
      }),
    enabled: !!params.from && !!params.to,
  });
}

export function usePicksQuery(weekDate: string | undefined) {
  return useQuery<{ week: string; items: PickResponse[] }, ApiError>({
    queryKey: queryKeys.screening.picks(weekDate ?? ""),
    queryFn: () => apiFetch(`/api/v1/weeks/${weekDate}/picks`),
    enabled: !!weekDate,
  });
}

export function useCompaniesQuery(
  weekDate: string | undefined,
  cursor: string | null,
) {
  return useQuery<
    { week: string; items: CompanyListItem[]; next_cursor: string | null },
    ApiError
  >({
    queryKey: queryKeys.screening.companies(weekDate ?? "", cursor),
    queryFn: () =>
      apiFetch(`/api/v1/weeks/${weekDate}/companies`, {
        query: { cursor: cursor ?? undefined, limit: 50 },
      }),
    enabled: !!weekDate,
  });
}

export function useCompanyQuery(
  weekDate: string | undefined,
  ticker: string | undefined,
) {
  return useQuery<CompanyDetail, ApiError>({
    queryKey: queryKeys.screening.company(weekDate ?? "", ticker ?? ""),
    queryFn: () => apiFetch(`/api/v1/weeks/${weekDate}/companies/${ticker}`),
    enabled: !!weekDate && !!ticker,
  });
}
