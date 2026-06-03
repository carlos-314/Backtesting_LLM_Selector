/**
 * `PageHeader` — título + acciones de cabecera (F3 §4.2).
 *
 * El título es un `<h1>`: al navegar entre vistas en SPA el foco va al `h1`
 * de la nueva vista (F3 §8 — accesibilidad). El componente acepta `ref`
 * vía `tabIndex={-1}` opcional para que la vista pueda gestionarlo.
 *
 * Contrato:
 *   PageHeader { title: string; actions?: ReactNode }
 *
 * Ejemplo:
 * ```tsx
 * <PageHeader
 *   title="Backtests"
 *   actions={
 *     <Button onClick={() => navigate("/backtests/nuevo")}>Lanzar</Button>
 *   }
 * />
 * ```
 */
import * as React from "react";

import { cn } from "@/lib/utils";

export interface PageHeaderProps {
  title: string;
  actions?: React.ReactNode;
  className?: string;
  description?: string;
}

export const PageHeader = React.forwardRef<HTMLHeadingElement, PageHeaderProps>(
  ({ title, actions, description, className }, ref) => (
    <div className={cn("mb-6 flex items-end justify-between gap-4", className)}>
      <div>
        <h1
          ref={ref}
          tabIndex={-1}
          className="text-2xl font-semibold tracking-tight focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          {title}
        </h1>
        {description && (
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        )}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  ),
);
PageHeader.displayName = "PageHeader";
