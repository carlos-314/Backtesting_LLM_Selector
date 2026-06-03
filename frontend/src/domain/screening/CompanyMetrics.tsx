/**
 * `CompanyMetrics` — métricas cuantitativas de la ficha (F3 §3.3, ADR-0002).
 *
 * El backend devuelve `raw_processed_stock` con TODAS las columnas. Aquí
 * extraemos un subconjunto canónico (5 bloques, ADR-0002) y lo pintamos.
 *
 * **Regla null≠0** (F2 §6.4, F3 §5): nunca pintamos `0` por un `null`.
 * `formatPercent`/`formatNumber` ya devuelven "—" si el valor es null.
 */
import { formatNumber, formatPercent } from "@/lib/utils";

interface RawRow {
  [key: string]: unknown;
}

export interface CompanyMetricsProps {
  raw: Record<string, unknown> | null;
}

interface MetricSpec {
  key: string;
  label: string;
  format: "number" | "percent" | "currency";
}

// Subconjunto canónico de ADR-0002. Las claves usan el casing original de la
// legacy (`processed_stocks`) porque el backend devuelve el row casi tal cual.
const BLOCKS: { title: string; items: MetricSpec[] }[] = [
  {
    title: "Valoración",
    items: [
      { key: "MOD1Y EV/EBIT", label: "EV/EBIT 1Y", format: "number" },
      { key: "MOD1Y EV/EBITDA", label: "EV/EBITDA 1Y", format: "number" },
      { key: "MOD1Y PER", label: "PER 1Y", format: "number" },
      { key: "MOD1Y P/FCF", label: "P/FCF 1Y", format: "number" },
    ],
  },
  {
    title: "Crecimiento",
    items: [
      { key: "GrowthRevenue_1Y", label: "Revenue Growth 1Y", format: "percent" },
      { key: "GrowthRevenueEst_1Y", label: "Estimated Growth 1Y", format: "percent" },
      { key: "AnalRevGrowth", label: "Analyst Rev Growth", format: "percent" },
    ],
  },
  {
    title: "Calidad",
    items: [
      { key: "ROCEROIconGODWILL_1Y", label: "ROCE/ROI 1Y", format: "percent" },
      { key: "NetDebtEbitda_1Y", label: "NetDebt/EBITDA 1Y", format: "number" },
      { key: "MedianGrossMargin", label: "Gross Margin (mediana)", format: "percent" },
    ],
  },
  {
    title: "Retorno al accionista",
    items: [
      { key: "AnnualPercentBuyback_3Y", label: "Buyback Yield 3Y", format: "percent" },
      { key: "DividendYield_3Y", label: "Dividend Yield 3Y", format: "percent" },
    ],
  },
  {
    title: "Mercado",
    items: [
      { key: "StockPrice", label: "Cotización", format: "number" },
      { key: "AverageVolume", label: "Volumen medio", format: "number" },
      { key: "CAGRPOT", label: "CAGR Potencial", format: "percent" },
    ],
  },
];

export function CompanyMetrics({ raw }: CompanyMetricsProps) {
  return (
    <div className="grid gap-6 md:grid-cols-2">
      {BLOCKS.map((b) => (
        <section
          key={b.title}
          className="rounded-md border bg-card p-4"
          aria-labelledby={`metrics-${b.title}`}
        >
          <h3 id={`metrics-${b.title}`} className="mb-3 text-sm font-semibold">
            {b.title}
          </h3>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            {b.items.map((m) => (
              <MetricRow key={m.key} spec={m} raw={raw} />
            ))}
          </dl>
        </section>
      ))}
    </div>
  );
}

function MetricRow({ spec, raw }: { spec: MetricSpec; raw: RawRow | null }) {
  const v = raw?.[spec.key];
  const num = typeof v === "number" ? v : v == null ? null : Number(v);
  const safe = num != null && Number.isFinite(num) ? num : null;

  return (
    <>
      <dt className="text-muted-foreground">{spec.label}</dt>
      <dd className="text-right font-medium tabular-nums">
        {spec.format === "percent"
          ? formatPercent(safe)
          : spec.format === "number"
            ? formatNumber(safe)
            : formatNumber(safe)}
      </dd>
    </>
  );
}
