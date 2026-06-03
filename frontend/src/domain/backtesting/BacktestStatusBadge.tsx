/**
 * `BacktestStatusBadge` — 5 estados del ciclo (F3 §3.3, §5.4, F2 §5.2).
 *
 * F3 §8: color no es único canal — cada estado lleva texto. (Iconos serían
 * un canal extra; los omitimos por simplicidad, el texto basta).
 */
import { Badge } from "@/components/ui/badge";
import type { BacktestStatus } from "@/lib/queries/backtests";

const LABEL: Record<BacktestStatus, string> = {
  pending: "En cola",
  running: "Ejecutando",
  completed: "Completado",
  failed: "Fallido",
  cancelled: "Cancelado",
};

const VARIANT: Record<BacktestStatus, "default" | "secondary" | "destructive" | "outline"> = {
  pending: "outline",
  running: "default",
  completed: "secondary",
  failed: "destructive",
  cancelled: "outline",
};

export function BacktestStatusBadge({ status }: { status: BacktestStatus }) {
  return (
    <Badge variant={VARIANT[status]}>
      <span>{LABEL[status]}</span>
    </Badge>
  );
}
