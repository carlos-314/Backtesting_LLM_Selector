/**
 * Claves canónicas de TanStack Query para invalidación tabulada (F3 §6.4).
 *
 * Centralizar las claves aquí evita typos y permite invalidar familias
 * enteras desde el `mapa de invalidación`.
 */

export const queryKeys = {
  auth: {
    me: () => ["auth", "me"] as const,
  },
  screening: {
    all: () => ["screening"] as const,
    weeks: (params?: { from?: string; to?: string }) =>
      ["screening", "weeks", params ?? {}] as const,
    picks: (weekDate: string) => ["screening", "picks", weekDate] as const,
    companies: (weekDate: string, cursor?: string | null) =>
      ["screening", "companies", weekDate, cursor ?? null] as const,
    company: (weekDate: string, ticker: string) =>
      ["screening", "company", weekDate, ticker] as const,
    matrix: (from: string, to: string) =>
      ["screening", "matrix", from, to] as const,
  },
  backtests: {
    all: () => ["backtests"] as const,
    list: (params?: { status?: string; cursor?: string | null }) =>
      ["backtests", "list", params ?? {}] as const,
    detail: (id: string) => ["backtests", "detail", id] as const,
    result: (id: string) => ["backtests", "result", id] as const,
    snapshot: (id: string) => ["backtests", "snapshot", id] as const,
  },
  admin: {
    users: () => ["admin", "users"] as const,
  },
};
