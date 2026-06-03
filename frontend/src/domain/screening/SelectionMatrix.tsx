/**
 * `SelectionMatrix` — rejilla empresa × semana (F3 §3.3, §1.5).
 *
 * Pieza difícil nº1. Renderiza el dato dispersos de `/api/v1/screening/matrix`
 * (ADR-0001). A la escala confirmada (decenas × ~26-156) no necesita
 * virtualización; tabla CSS con sticky.
 *
 * Estados de celda (F3 §5.3):
 *   - selected: pick del run resuelto (color principal + icono).
 *   - in_universe: analizada pero no seleccionada (gris).
 *   - missing: no aparece en la celda → el ticker no estuvo ese run.
 *
 * F3 §8 "color no es único canal": cada estado tiene texto/icono distinto.
 */
import { Check, Minus } from "lucide-react";
import { useMemo } from "react";
import { useNavigate } from "@tanstack/react-router";

import { cn } from "@/lib/utils";

import { TickerLabel } from "./TickerLabel";
import { WeekBadge } from "./WeekBadge";

export interface MatrixData {
  weeks: { week_date: string; run_code: string; resolved_run_id: number }[];
  companies: {
    ticker: string;
    name: string | null;
    country: string | null;
    currency: string | null;
  }[];
  cells: {
    ticker: string;
    week_date: string;
    state: "selected" | "in_universe";
  }[];
}

export interface SelectionMatrixProps {
  data: MatrixData;
  onCellClick?: (weekDate: string, ticker: string) => void;
}

export function SelectionMatrix({ data, onCellClick }: SelectionMatrixProps) {
  const navigate = useNavigate();

  // Index cells (ticker, week_date) → state
  const cellIndex = useMemo(() => {
    const m = new Map<string, "selected" | "in_universe">();
    for (const c of data.cells) m.set(`${c.ticker}|${c.week_date}`, c.state);
    return m;
  }, [data.cells]);

  if (data.weeks.length === 0 || data.companies.length === 0) {
    return (
      <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
        No hay datos para este rango.
      </div>
    );
  }

  const defaultClick = (weekDate: string, ticker: string) => {
    void navigate({ to: "/mapa/$semana/$ticker", params: { semana: weekDate, ticker } });
  };

  return (
    <div className="relative overflow-auto rounded-md border" role="region" aria-label="Mapa histórico de selección">
      <table className="border-collapse text-xs">
        <thead className="bg-card">
          <tr>
            <th
              scope="col"
              className="sticky left-0 top-0 z-20 min-w-[180px] border-b border-r bg-card px-3 py-2 text-left font-medium"
            >
              Empresa
            </th>
            {data.weeks.map((w) => (
              <th
                key={w.week_date}
                scope="col"
                className="sticky top-0 z-10 min-w-[80px] border-b bg-card px-2 py-2 text-center font-medium"
                title={w.run_code}
              >
                <WeekBadge weekDate={w.week_date} />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.companies.map((c) => (
            <tr key={c.ticker} className="border-b">
              <th
                scope="row"
                className="sticky left-0 z-10 border-r bg-background px-3 py-2 text-left font-normal"
              >
                <TickerLabel
                  ticker={c.ticker}
                  name={c.name}
                  country={c.country}
                  currency={c.currency}
                  size="sm"
                />
              </th>
              {data.weeks.map((w) => {
                const state = cellIndex.get(`${c.ticker}|${w.week_date}`);
                return (
                  <Cell
                    key={`${c.ticker}|${w.week_date}`}
                    state={state}
                    label={`${c.ticker} en semana ${w.week_date}`}
                    onClick={() =>
                      onCellClick
                        ? onCellClick(w.week_date, c.ticker)
                        : defaultClick(w.week_date, c.ticker)
                    }
                  />
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Cell({
  state,
  label,
  onClick,
}: {
  state: "selected" | "in_universe" | undefined;
  label: string;
  onClick: () => void;
}) {
  // F3 §8: color NO es único canal — añadimos icono/texto.
  if (state === "selected") {
    return (
      <td className="p-0">
        <button
          type="button"
          onClick={onClick}
          aria-label={`${label}: seleccionada`}
          className="flex h-9 w-full items-center justify-center bg-primary text-primary-foreground transition-opacity hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset"
        >
          <Check className="h-4 w-4" aria-hidden="true" />
          <span className="sr-only">Seleccionada</span>
        </button>
      </td>
    );
  }
  if (state === "in_universe") {
    return (
      <td className="p-0">
        <button
          type="button"
          onClick={onClick}
          aria-label={`${label}: en universo`}
          className={cn(
            "flex h-9 w-full items-center justify-center text-muted-foreground transition-opacity hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset",
            "bg-muted",
          )}
        >
          <Minus className="h-4 w-4" aria-hidden="true" />
          <span className="sr-only">En universo</span>
        </button>
      </td>
    );
  }
  return (
    <td
      aria-label={`${label}: no estuvo`}
      className="h-9 bg-card"
      title="No estuvo"
    />
  );
}
