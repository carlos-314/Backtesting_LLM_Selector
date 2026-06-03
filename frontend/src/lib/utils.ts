import { type ClassValue, clsx } from 'clsx';

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

export function formatPercent(value: number | null | undefined): string {
  if (value == null) return '-';
  return `${(value * 100).toFixed(2)}%`;
}

export function formatNumber(value: number | null | undefined, decimals = 2): string {
  if (value == null) return '-';
  return value.toFixed(decimals);
}

export function formatCurrency(value: number | null | undefined, currency = 'EUR'): string {
  if (value == null) return '-';
  return new Intl.NumberFormat('es-ES', { style: 'currency', currency }).format(value);
}
