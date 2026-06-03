/**
 * `BacktestProgress` — progreso honesto por semanas, no % inventado
 * (F3 §3.3, §5.4, F2 §5.2 auditoría M1).
 *
 * Estados:
 *  - pending → sin barra, solo texto "En cola".
 *  - running → barra con `weeks_processed / weeks_total`.
 *  - terminal → no se renderiza nada (la vista muestra resultado o error).
 */
import type { BacktestStatus } from "@/lib/queries/backtests";

export interface BacktestProgressProps {
  status: BacktestStatus;
  weeksTotal: number | null;
  weeksProcessed: number | null;
}

export function BacktestProgress({
  status,
  weeksTotal,
  weeksProcessed,
}: BacktestProgressProps) {
  if (status === "pending") {
    return (
      <div role="status" aria-live="polite" className="text-sm text-muted-foreground">
        En cola — esperando a un worker libre…
      </div>
    );
  }
  if (status !== "running") return null;

  const pct =
    weeksTotal && weeksTotal > 0 && weeksProcessed != null
      ? Math.min(100, Math.round((weeksProcessed / weeksTotal) * 100))
      : 0;

  return (
    <div role="status" aria-live="polite" className="space-y-2">
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">
          Procesando semanas: {weeksProcessed ?? 0} / {weeksTotal ?? "?"}
        </span>
        <span className="font-mono text-xs text-muted-foreground">{pct}%</span>
      </div>
      <div
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        className="h-2 w-full overflow-hidden rounded-full bg-secondary"
      >
        <div
          className="h-full bg-primary transition-[width] duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
