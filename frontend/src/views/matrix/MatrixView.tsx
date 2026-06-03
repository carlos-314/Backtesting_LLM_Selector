/**
 * V-MATRIX — Mapa histórico (F3 §1.3, §5.3, §6.1 I3).
 *
 * Ventana de semanas (`from`/`to`) parametriza la petición y vive **en la
 * vista**, no en `SelectionMatrix` (F3 §6.1 I3). 26 semanas por defecto.
 */
import * as React from "react";

import { DataState } from "@/components/base/DataState";
import { PageHeader } from "@/components/base/PageHeader";
import { Button } from "@/components/ui/button";
import { SelectionMatrix } from "@/domain/screening/SelectionMatrix";
import { useMatrixQuery } from "@/lib/queries/screening";

function monday(d: Date): Date {
  const out = new Date(d);
  out.setDate(out.getDate() - ((out.getDay() + 6) % 7));
  return out;
}
function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}
function addWeeks(d: Date, n: number): Date {
  const out = new Date(d);
  out.setDate(out.getDate() + n * 7);
  return out;
}

export function MatrixView() {
  const [windowWeeks, setWindowWeeks] = React.useState(26);
  const today = React.useMemo(() => monday(new Date()), []);
  const to = isoDate(today);
  const from = isoDate(addWeeks(today, -(windowWeeks - 1)));

  const query = useMatrixQuery({ from, to });

  const status =
    query.isLoading
      ? "loading"
      : query.error
        ? "error"
        : query.data && query.data.weeks.length === 0
          ? "empty"
          : "ready";

  return (
    <>
      <PageHeader
        title="Mapa histórico de selección"
        description={`Ventana: ${from} → ${to} (${windowWeeks} semanas)`}
        actions={
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setWindowWeeks((w) => Math.max(8, w - 8))}
              disabled={windowWeeks <= 8}
              aria-label="Reducir ventana"
            >
              −8 sem
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setWindowWeeks((w) => Math.min(156, w + 8))}
              disabled={windowWeeks >= 156}
              aria-label="Ampliar ventana"
            >
              +8 sem
            </Button>
          </div>
        }
      />
      <DataState
        status={status}
        data={query.data}
        error={query.error ?? undefined}
        onRetry={() => void query.refetch()}
      >
        {(data) => <SelectionMatrix data={data} />}
      </DataState>
    </>
  );
}
