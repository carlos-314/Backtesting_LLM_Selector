/**
 * `DataState<T>` — la columna vertebral del estrato 2 (F3 §3.3, §4.2).
 *
 * Normaliza los cuatro estados del consumo de datos:
 *  - `loading` → skeleton (override con `loadingSlot`)
 *  - `empty`   → `EmptyState` (override con `emptySlot`)
 *  - `error`   → `ErrorState` (override con `errorSlot`)
 *  - `ready`   → `children(data)` (render-prop tipado: dentro `data` está garantizado)
 *
 * Decisiones del contrato (F3 §4.2):
 *  - `status` explícito, no derivado de `data == null` (los `null` de F2 §6.4 son significativos).
 *  - Caso "ready" como render-prop: garantía por tipos del acceso seguro a `data`.
 *  - El reintento es parte del contrato del error: pasa `onRetry`.
 *  - NO maneja el ciclo asíncrono del backtest — eso es dominio (BacktestProgress, B3).
 *
 * Ejemplo:
 * ```tsx
 * const query = useWeeksQuery();
 * <DataState
 *   status={
 *     query.isLoading ? "loading"
 *     : query.error ? "error"
 *     : query.data && query.data.items.length === 0 ? "empty"
 *     : "ready"
 *   }
 *   data={query.data}
 *   error={query.error as ApiError | undefined}
 *   onRetry={() => query.refetch()}
 * >
 *   {(data) => <WeeksList weeks={data.items} />}
 * </DataState>
 * ```
 */
import * as React from "react";

import { EmptyState } from "@/components/base/EmptyState";
import { ErrorState } from "@/components/base/ErrorState";
import { Skeleton } from "@/components/ui/skeleton";
import type { ApiError } from "@/lib/api-error";

export type DataStateStatus = "loading" | "empty" | "error" | "ready";

export interface DataStateProps<T> {
  status: DataStateStatus;
  data?: T;
  error?: ApiError | { code: string; message: string };

  /** Render del caso "ready". Render-prop para garantizar `data` no-nulo. */
  children: (data: T) => React.ReactNode;

  loadingSlot?: React.ReactNode;
  emptySlot?: React.ReactNode;
  errorSlot?: (
    error: NonNullable<DataStateProps<T>["error"]>,
    retry: () => void,
  ) => React.ReactNode;
  onRetry?: () => void;
}

export function DataState<T>({
  status,
  data,
  error,
  children,
  loadingSlot,
  emptySlot,
  errorSlot,
  onRetry,
}: DataStateProps<T>) {
  if (status === "loading") {
    return <>{loadingSlot ?? <DefaultLoading />}</>;
  }
  if (status === "error") {
    if (!error) {
      // Defensa de tipos: si status==="error" sin error, lo señalamos.
      return (
        <ErrorState
          error={{ code: "internal_error", message: "Estado de error sin detalle" }}
          onRetry={onRetry}
        />
      );
    }
    if (errorSlot) return <>{errorSlot(error, onRetry ?? noop)}</>;
    return <ErrorState error={error} onRetry={onRetry} />;
  }
  if (status === "empty") {
    return <>{emptySlot ?? <EmptyState title="Sin datos" />}</>;
  }
  // status === "ready"
  if (data === undefined) {
    // En "ready" se espera dato. Tratamos como error defensivo en lugar
    // de permitir un crash silencioso.
    return (
      <ErrorState
        error={{ code: "internal_error", message: "Datos ausentes en estado ready" }}
        onRetry={onRetry}
      />
    );
  }
  return <>{children(data)}</>;
}

function DefaultLoading() {
  return (
    <div className="space-y-3" aria-busy="true" aria-live="polite">
      <Skeleton className="h-8 w-1/3" />
      <Skeleton className="h-32 w-full" />
      <Skeleton className="h-32 w-full" />
    </div>
  );
}

function noop() {}
