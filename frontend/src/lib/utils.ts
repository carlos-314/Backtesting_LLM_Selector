/**
 * Utilidades transversales del frontend.
 */
import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Combinador de clases Tailwind: `clsx` para condicionales + `twMerge` para
 * resolver conflictos (p.ej. `p-2 p-4` queda en `p-4`).
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Formatea un porcentaje. `null`/`undefined` → "—" (regla null≠0 F3 §5). */
export function formatPercent(
  value: number | null | undefined,
  decimals = 2,
): string {
  if (value == null) return "—";
  return `${(value * 100).toFixed(decimals)}%`;
}

/** Formatea un número decimal. `null`/`undefined` → "—". */
export function formatNumber(
  value: number | null | undefined,
  decimals = 2,
): string {
  if (value == null) return "—";
  return value.toFixed(decimals);
}

/** Formatea importe en divisa (default USD día uno F0). */
export function formatCurrency(
  value: number | string | null | undefined,
  currency = "USD",
): string {
  if (value == null) return "—";
  const n = typeof value === "string" ? Number(value) : value;
  if (!Number.isFinite(n)) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(
    n,
  );
}
