/**
 * `EmptyState` — "no hay nada aquí" (F3 §4.2).
 *
 * Distinto de `error` y de `loading`. F3 §5.1: petición correcta sin datos.
 *
 * Contrato:
 *   EmptyState {
 *     title: string;
 *     description?: string;
 *     action?: { label: string; onAction: () => void };
 *   }
 *
 * Ejemplo:
 * ```tsx
 * <EmptyState
 *   title="Sin backtests todavía"
 *   description="Lanza tu primer backtest desde el botón superior."
 *   action={{ label: "Lanzar backtest", onAction: () => navigate("/backtests/nuevo") }}
 * />
 * ```
 */
import { Inbox } from "lucide-react";

import { Button } from "@/components/ui/button";

export interface EmptyStateProps {
  title: string;
  description?: string;
  action?: { label: string; onAction: () => void };
  icon?: React.ReactNode;
}

export function EmptyState({ title, description, action, icon }: EmptyStateProps) {
  return (
    <div
      className="flex flex-col items-center justify-center gap-3 rounded-md border border-dashed bg-card p-12 text-center"
      role="status"
    >
      <div className="text-muted-foreground" aria-hidden="true">
        {icon ?? <Inbox className="h-8 w-8" />}
      </div>
      <h2 className="text-base font-semibold text-foreground">{title}</h2>
      {description && (
        <p className="max-w-md text-sm text-muted-foreground">{description}</p>
      )}
      {action && (
        <div className="mt-2">
          <Button variant="outline" size="sm" onClick={action.onAction}>
            {action.label}
          </Button>
        </div>
      )}
    </div>
  );
}
