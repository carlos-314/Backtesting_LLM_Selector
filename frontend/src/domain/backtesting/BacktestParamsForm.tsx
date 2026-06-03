/**
 * `BacktestParamsForm` — formulario de lanzamiento (F3 §3.3, F2 §6.5).
 *
 * F2 §5.2/§6.5: día uno 1/N (no expone otra ponderación) y USD (no expone
 * otra divisa). `strategy_code` y `benchmark_code` fijos por ahora.
 *
 * Validación con zod en cliente + el 422 del servidor es la autoridad (F3 §5.3).
 */
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { FormField } from "@/components/base/FormField";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const schema = z.object({
  name: z.string().min(1, "Pon un nombre"),
  period_start: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Formato YYYY-MM-DD"),
  period_end: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Formato YYYY-MM-DD"),
  initial_capital: z
    .string()
    .regex(/^\d+(\.\d+)?$/, "Importe numérico")
    .refine((v) => Number(v) > 0, "Debe ser mayor que 0"),
});

export type BacktestParamsValues = z.infer<typeof schema>;

export interface BacktestParamsFormProps {
  defaultValues?: Partial<BacktestParamsValues>;
  onSubmit: (values: BacktestParamsValues) => void | Promise<void>;
  isSubmitting?: boolean;
  serverErrorByField?: Partial<Record<keyof BacktestParamsValues, string>>;
}

export function BacktestParamsForm({
  defaultValues,
  onSubmit,
  isSubmitting,
  serverErrorByField,
}: BacktestParamsFormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<BacktestParamsValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: "",
      period_start: "",
      period_end: "",
      initial_capital: "100000",
      ...defaultValues,
    },
  });

  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      className="space-y-4"
      noValidate
      aria-label="Lanzar backtest"
    >
      <FormField
        label="Nombre"
        htmlFor="bt-name"
        required
        error={errors.name?.message ?? serverErrorByField?.name}
      >
        <Input
          id="bt-name"
          placeholder="Mi primer backtest"
          aria-invalid={!!errors.name || !!serverErrorByField?.name}
          {...register("name")}
        />
      </FormField>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <FormField
          label="Periodo inicio"
          htmlFor="bt-start"
          required
          hint="Fecha del lunes (NY) del primer semana"
          error={errors.period_start?.message ?? serverErrorByField?.period_start}
        >
          <Input
            id="bt-start"
            type="date"
            aria-invalid={!!errors.period_start}
            {...register("period_start")}
          />
        </FormField>
        <FormField
          label="Periodo fin"
          htmlFor="bt-end"
          required
          hint="Fecha del lunes (NY) de la última semana"
          error={errors.period_end?.message ?? serverErrorByField?.period_end}
        >
          <Input
            id="bt-end"
            type="date"
            aria-invalid={!!errors.period_end}
            {...register("period_end")}
          />
        </FormField>
      </div>

      <FormField
        label="Capital inicial (USD)"
        htmlFor="bt-cap"
        required
        hint="Día uno la divisa base es USD y la ponderación es 1/N (F0/F2)."
        error={errors.initial_capital?.message ?? serverErrorByField?.initial_capital}
      >
        <Input
          id="bt-cap"
          inputMode="decimal"
          aria-invalid={!!errors.initial_capital}
          {...register("initial_capital")}
        />
      </FormField>

      <div className="flex justify-end">
        <Button type="submit" isLoading={isSubmitting}>
          Lanzar backtest
        </Button>
      </div>
    </form>
  );
}
