/**
 * `CompanyQualitative` — bloques cualitativos del LLM (F3 §3.3, ADR-0002).
 *
 * Los campos JSONB de la legacy (`AIDirectiva2`, `calidadDirectiva5`,
 * `potencialFraude8`, etc.) son estructuras libres. Día uno mostramos
 * cada bloque con su `JSON.stringify` formateado en `<details>` para
 * no asumir esquema interno. ADR-0002 define el catálogo definitivo
 * pendiente de validación de producto.
 */

interface RawRow {
  [key: string]: unknown;
}

const QUALITATIVE_KEYS: { key: string; label: string }[] = [
  { key: "AIDirectiva2", label: "Análisis directivo" },
  { key: "aValoresCrecimiento2", label: "Valores de crecimiento" },
  { key: "calidadDirectiva5", label: "Calidad de la directiva" },
  { key: "fijacionPrecios2", label: "Fijación de precios" },
  { key: "guidanceSearch2", label: "Búsqueda en guidance" },
  { key: "potencialFraude8", label: "Potencial de fraude" },
  { key: "sensibilidadMacro1", label: "Sensibilidad macro" },
  { key: "evoMarketShare2", label: "Evolución cuota de mercado" },
  { key: "customerConcentrationRisk", label: "Concentración de clientes" },
];

export interface CompanyQualitativeProps {
  raw: Record<string, unknown> | null;
  finalDossier?: string | null;
}

export function CompanyQualitative({ raw }: CompanyQualitativeProps) {
  const finalDossier =
    typeof raw?.ai_finalDossier === "string" ? raw.ai_finalDossier : null;

  return (
    <div className="space-y-4">
      {finalDossier && (
        <section className="rounded-md border bg-card p-4">
          <h3 className="mb-2 text-sm font-semibold">Dossier final</h3>
          <p className="whitespace-pre-wrap text-sm text-muted-foreground">
            {finalDossier}
          </p>
        </section>
      )}
      <div className="grid gap-3 md:grid-cols-2">
        {QUALITATIVE_KEYS.map((q) => (
          <QualitativeBlock key={q.key} spec={q} raw={raw} />
        ))}
      </div>
    </div>
  );
}

function QualitativeBlock({
  spec,
  raw,
}: {
  spec: { key: string; label: string };
  raw: RawRow | null;
}) {
  const value = raw?.[spec.key];
  if (value == null || (typeof value === "object" && Object.keys(value as object).length === 0)) {
    return (
      <details className="rounded-md border bg-card p-3 text-sm">
        <summary className="cursor-pointer font-medium">{spec.label}</summary>
        <p className="mt-2 text-xs text-muted-foreground">Sin análisis</p>
      </details>
    );
  }
  return (
    <details className="rounded-md border bg-card p-3 text-sm">
      <summary className="cursor-pointer font-medium">{spec.label}</summary>
      <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap break-words text-xs text-muted-foreground">
        {JSON.stringify(value, null, 2)}
      </pre>
    </details>
  );
}
