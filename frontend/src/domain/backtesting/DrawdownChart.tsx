/**
 * `DrawdownChart` — curva de drawdowns con N series (F3 §4.3).
 *
 * Idem `EquityChart` en contrato (N series, recharts) pero los valores
 * son caídas relativas en %. Se calcula in-componente a partir del equity
 * point máximo previo.
 */
import { useMemo } from "react";

import { EquityChart, type EquitySeries } from "./EquityChart";

export interface DrawdownChartProps {
  series: EquitySeries[];
  height?: number;
  showLegend?: boolean;
}

function toDrawdown(series: EquitySeries): EquitySeries {
  let peak = -Infinity;
  return {
    ...series,
    points: series.points.map((p) => {
      peak = Math.max(peak, p.value);
      const dd = peak > 0 ? (p.value - peak) / peak : 0;
      return { date: p.date, value: dd };
    }),
  };
}

export function DrawdownChart({ series, height, showLegend }: DrawdownChartProps) {
  const ddSeries = useMemo(() => series.map(toDrawdown), [series]);
  return <EquityChart series={ddSeries} height={height} showLegend={showLegend} />;
}
