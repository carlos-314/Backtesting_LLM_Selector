/**
 * V-BT-LANZAR — Formulario de lanzamiento (F3 §1.3, §5.3).
 *
 * Tras éxito (202) → navega al detalle (`/backtests/{id}`) y dispara toast.
 * F3 §6.4: la mutación invalida `backtests` (lo hace `useCreateBacktestMutation`).
 */
import { useNavigate } from "@tanstack/react-router";
import * as React from "react";

import { ErrorState } from "@/components/base/ErrorState";
import { PageHeader } from "@/components/base/PageHeader";
import { toast } from "@/components/ui/toaster";
import {
  BacktestParamsForm,
  type BacktestParamsValues,
} from "@/domain/backtesting/BacktestParamsForm";
import { ApiError } from "@/lib/api-error";
import { useCreateBacktestMutation } from "@/lib/queries/backtests";

export function BacktestNewView() {
  const navigate = useNavigate();
  const create = useCreateBacktestMutation();
  const [error, setError] = React.useState<ApiError | null>(null);
  const [serverErrorByField, setServerErrorByField] = React.useState<
    Partial<Record<keyof BacktestParamsValues, string>> | undefined
  >();

  const onSubmit = async (values: BacktestParamsValues) => {
    setError(null);
    setServerErrorByField(undefined);
    try {
      const bt = await create.mutateAsync(values);
      toast.success("Backtest en cola");
      void navigate({ to: "/backtests/$id", params: { id: bt.id } });
    } catch (e) {
      if (e instanceof ApiError) {
        if (e.code === "invalid_period") {
          setServerErrorByField({
            period_start: e.message,
            period_end: e.message,
          });
        } else if (e.code === "invalid_capital") {
          setServerErrorByField({ initial_capital: e.message });
        } else {
          setError(e);
        }
      }
    }
  };

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader
        title="Lanzar backtest"
        description="Equiponderación 1/N y divisa USD día uno (F0/F2)."
      />
      <BacktestParamsForm
        onSubmit={onSubmit}
        isSubmitting={create.isPending}
        serverErrorByField={serverErrorByField}
      />
      {error && (
        <div className="mt-4">
          <ErrorState error={error} />
        </div>
      )}
    </div>
  );
}
