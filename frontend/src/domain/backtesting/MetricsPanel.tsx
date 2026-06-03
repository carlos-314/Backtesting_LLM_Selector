/**
 * `MetricsPanel` — métricas núcleo en N columnas (F3 §4.3).
 *
 * Aridad-N: día uno una columna (un backtest); al comparar (F3 §1.5)
 * múltiples columnas yuxtapuestas.
 *
 * Reglas null≠0 — `formatPercent`/`formatNumber` devuelven "—" si null.
 */
import { formatNumber, formatPercent } from "@/lib/utils";

export interface MetricsColumn {
  id: string;
  label: string;
  metrics: {
    totalReturn: string | null;
    cagr: string | null;
    volatility: string | null;
    sharpe: string | null;
    maxDrawdown: string | null;
  };
}

export interface MetricsPanelProps {
  columns: MetricsColumn[];
}

function toNum(s: string | null): number | null {
  if (s == null) return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

const ROWS: { key: keyof MetricsColumn["metrics"]; label: string; fmt: "percent" | "number" }[] = [
  { key: "totalReturn", label: "Retorno total", fmt: "percent" },
  { key: "cagr", label: "CAGR", fmt: "percent" },
  { key: "volatility", label: "Volatilidad", fmt: "percent" },
  { key: "sharpe", label: "Sharpe", fmt: "number" },
  { key: "maxDrawdown", label: "Max Drawdown", fmt: "percent" },
];

export function MetricsPanel({ columns }: MetricsPanelProps) {
  if (columns.length === 0) {
    return (
      <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
        Sin métricas para mostrar
      </div>
    );
  }
  return (
    <div className="overflow-auto rounded-md border bg-card">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="border-b bg-muted/40">
            <th scope="col" className="px-3 py-2 text-left font-medium">
              Métrica
            </th>
            {columns.map((c) => (
              <th key={c.id} scope="col" className="px-3 py-2 text-right font-medium">
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ROWS.map((row) => (
            <tr key={row.key} className="border-b last:border-0">
              <th scope="row" className="px-3 py-2 text-left font-normal text-muted-foreground">
                {row.label}
              </th>
              {columns.map((c) => {
                const num = toNum(c.metrics[row.key]);
                return (
                  <td key={c.id} className="px-3 py-2 text-right font-medium tabular-nums">
                    {row.fmt === "percent" ? formatPercent(num) : formatNumber(num)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
