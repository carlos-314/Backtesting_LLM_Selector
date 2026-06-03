/**
 * `EquityChart` — curva(s) de equity con N series (F3 §4.3, ADR M5).
 *
 * Aridad-N: clave para "comparar backtests" como costura (F3 §1.5).
 * El componente no cambia entre 1 serie (cartera) y N series (cartera + benchmark + comparados).
 *
 * Construido con recharts (ADR-0001 M5). Eje X = fechas YYYY-MM-DD, eje Y = USD.
 */
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export interface EquitySeries {
  id: string;
  label: string;
  points: { date: string; value: number }[];
  role?: "portfolio" | "benchmark";
}

export interface EquityChartProps {
  series: EquitySeries[];
  height?: number;
  showLegend?: boolean;
}

// Paleta accesible y consistente. `portfolio` → primario; `benchmark` → muted.
const COLORS = ["#0f172a", "#94a3b8", "#0284c7", "#16a34a", "#dc2626", "#9333ea"];

function colorFor(s: EquitySeries, idx: number): string {
  if (s.role === "portfolio") return COLORS[0];
  if (s.role === "benchmark") return COLORS[1];
  return COLORS[(idx % (COLORS.length - 2)) + 2];
}

export function EquityChart({ series, height = 320, showLegend = true }: EquityChartProps) {
  // Unir todas las fechas (sin duplicar) en un array de puntos para recharts
  const dates = Array.from(
    new Set(series.flatMap((s) => s.points.map((p) => p.date))),
  ).sort();

  const data = dates.map((d) => {
    const row: Record<string, string | number> = { date: d };
    for (const s of series) {
      const pt = s.points.find((p) => p.date === d);
      if (pt) row[s.id] = pt.value;
    }
    return row;
  });

  if (series.length === 0 || data.length === 0) {
    return (
      <div
        role="img"
        aria-label="Curva de equity sin datos"
        className="flex h-[320px] w-full items-center justify-center rounded-md border border-dashed text-sm text-muted-foreground"
      >
        Sin datos para graficar
      </div>
    );
  }

  return (
    <div role="img" aria-label="Curva de equity">
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
          <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" />
          <XAxis dataKey="date" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip
            contentStyle={{
              background: "hsl(var(--popover))",
              border: "1px solid hsl(var(--border))",
              borderRadius: 6,
              fontSize: 12,
            }}
          />
          {showLegend && <Legend wrapperStyle={{ fontSize: 12 }} />}
          {series.map((s, i) => (
            <Line
              key={s.id}
              type="monotone"
              dataKey={s.id}
              name={s.label}
              stroke={colorFor(s, i)}
              dot={false}
              strokeWidth={s.role === "portfolio" ? 2.5 : 1.5}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
