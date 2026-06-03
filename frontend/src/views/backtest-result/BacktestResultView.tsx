/**
 * V-BT-RESULTADO — Resultado con polling (F3 §1.3, §5.3, §6.5).
 *
 * Dos capas:
 *  - Petición (polling): carga / 404 / fallo transitorio.
 *  - Dominio: pending / running (progreso honesto) / completed (result+charts) /
 *    failed (error legible) / cancelled.
 *
 * Cancelación: ConfirmDialog destructive (F3 §5.3). 409 al cancelar un
 * terminal → recarga + toast (sin error rojo).
 */
import { useParams } from "@tanstack/react-router";
import * as React from "react";

import { ConfirmDialog } from "@/components/base/ConfirmDialog";
import { DataState } from "@/components/base/DataState";
import { ErrorState } from "@/components/base/ErrorState";
import { PageHeader } from "@/components/base/PageHeader";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/toaster";
import { BacktestProgress } from "@/domain/backtesting/BacktestProgress";
import { BacktestStatusBadge } from "@/domain/backtesting/BacktestStatusBadge";
import { EquityChart, type EquitySeries } from "@/domain/backtesting/EquityChart";
import { DrawdownChart } from "@/domain/backtesting/DrawdownChart";
import { MetricsPanel } from "@/domain/backtesting/MetricsPanel";
import { RoleGate } from "@/domain/screening/RoleGate";
import { ApiError } from "@/lib/api-error";
import {
  useBacktestQuery,
  useBacktestResultQuery,
  useCancelBacktestMutation,
} from "@/lib/queries/backtests";

export function BacktestResultView() {
  const { id } = useParams({ strict: false }) as { id?: string };

  const bt = useBacktestQuery(id, { polling: true });
  const isCompleted = bt.data?.status === "completed";
  const result = useBacktestResultQuery(id, isCompleted);
  const cancel = useCancelBacktestMutation();
  const [confirmOpen, setConfirmOpen] = React.useState(false);

  const onConfirmCancel = async () => {
    if (!id) return;
    try {
      await cancel.mutateAsync(id);
      toast.success("Backtest cancelado");
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        // F3 §6.3 C2: 409 = vista caduca, no error rojo. Refrescamos.
        await bt.refetch();
        toast("El backtest ya había terminado — vista actualizada");
      } else if (e instanceof ApiError) {
        toast.error(e.message);
      }
    } finally {
      setConfirmOpen(false);
    }
  };

  const status = bt.isLoading ? "loading" : bt.error ? "error" : "ready";

  return (
    <DataState
      status={status}
      data={bt.data}
      error={bt.error ?? undefined}
      onRetry={() => void bt.refetch()}
    >
      {(data) => (
        <div className="space-y-6">
          <PageHeader
            title={data.name}
            description={`Periodo: ${data.period.start} → ${data.period.end} · ${data.strategy_code} · ${data.benchmark_code}`}
            actions={
              <div className="flex items-center gap-3">
                <BacktestStatusBadge status={data.status} />
                {(data.status === "pending" || data.status === "running") && (
                  <RoleGate allow={["analyst", "admin"]}>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => setConfirmOpen(true)}
                    >
                      Cancelar
                    </Button>
                  </RoleGate>
                )}
              </div>
            }
          />

          {(data.status === "pending" || data.status === "running") && (
            <div className="rounded-md border bg-card p-4">
              <BacktestProgress
                status={data.status}
                weeksTotal={data.weeks_total}
                weeksProcessed={data.weeks_processed}
              />
            </div>
          )}

          {data.status === "failed" && data.error && (
            <ErrorState
              error={{ code: data.error.code, message: data.error.message }}
            />
          )}

          {data.status === "cancelled" && (
            <div
              role="status"
              className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground"
            >
              El backtest fue cancelado. No hay resultado.
            </div>
          )}

          {isCompleted && (
            <ResultBlock query={result} backtestId={data.id} name={data.name} />
          )}

          <ConfirmDialog
            open={confirmOpen}
            onOpenChange={setConfirmOpen}
            title="¿Cancelar este backtest?"
            description="El backtest pasará a estado 'cancelled' y dejará de procesarse."
            confirmLabel="Sí, cancelar"
            variant="destructive"
            onConfirm={onConfirmCancel}
            isPending={cancel.isPending}
          />
        </div>
      )}
    </DataState>
  );
}

function ResultBlock({
  query,
  backtestId,
  name,
}: {
  query: ReturnType<typeof useBacktestResultQuery>;
  backtestId: string;
  name: string;
}) {
  const s = query.isLoading ? "loading" : query.error ? "error" : "ready";

  return (
    <DataState
      status={s}
      data={query.data}
      error={query.error ?? undefined}
      onRetry={() => void query.refetch()}
    >
      {(result) => {
        const series: EquitySeries[] = [
          {
            id: "portfolio",
            label: "Cartera",
            role: "portfolio",
            points: result.equity_curve
              .filter((p) => p.series === "portfolio")
              .map((p) => ({ date: p.date, value: Number(p.value) })),
          },
          {
            id: "benchmark",
            label: "Benchmark",
            role: "benchmark",
            points: result.equity_curve
              .filter((p) => p.series === "benchmark")
              .map((p) => ({ date: p.date, value: Number(p.value) })),
          },
        ];

        return (
          <div className="space-y-6">
            <MetricsPanel
              columns={[
                {
                  id: backtestId,
                  label: name,
                  metrics: {
                    totalReturn: result.metrics.total_return,
                    cagr: result.metrics.cagr,
                    volatility: result.metrics.volatility,
                    sharpe: result.metrics.sharpe,
                    maxDrawdown: result.metrics.max_drawdown,
                  },
                },
              ]}
            />
            <section className="rounded-md border bg-card p-4">
              <h3 className="mb-2 text-sm font-semibold">Curva de capital</h3>
              <EquityChart series={series} />
            </section>
            <section className="rounded-md border bg-card p-4">
              <h3 className="mb-2 text-sm font-semibold">Drawdowns</h3>
              <DrawdownChart series={series} />
            </section>
            <p className="text-xs text-muted-foreground">
              Snapshot: {result.snapshot_summary.weeks} semanas (
              {result.snapshot_summary.first_week} → {result.snapshot_summary.last_week}).
            </p>
          </div>
        );
      }}
    </DataState>
  );
}
