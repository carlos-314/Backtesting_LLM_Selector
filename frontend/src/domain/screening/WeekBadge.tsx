/**
 * `WeekBadge` — representa una `Week` (F3 §3.3).
 *
 * Muestra la fecha del lunes canónico (F2 §4.3) en formato ISO o
 * localizado (configurable por prop).
 */
import { Badge } from "@/components/ui/badge";

export interface WeekBadgeProps {
  weekDate: string; // YYYY-MM-DD del lunes NY
  variant?: "default" | "secondary" | "outline";
}

export function WeekBadge({ weekDate, variant = "outline" }: WeekBadgeProps) {
  return <Badge variant={variant}><time dateTime={weekDate}>{weekDate}</time></Badge>;
}
