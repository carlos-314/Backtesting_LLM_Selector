/**
 * `TickerLabel` — símbolo + nombre + país/divisa (F3 §3.3).
 */
import { cn } from "@/lib/utils";

export interface TickerLabelProps {
  ticker: string;
  name?: string | null;
  country?: string | null;
  currency?: string | null;
  size?: "sm" | "md";
  className?: string;
}

export function TickerLabel({
  ticker,
  name,
  country,
  currency,
  size = "md",
  className,
}: TickerLabelProps) {
  return (
    <span className={cn("inline-flex flex-col leading-tight", className)}>
      <span
        className={cn(
          "font-mono font-semibold",
          size === "md" ? "text-sm" : "text-xs",
        )}
      >
        {ticker}
      </span>
      {(name || country || currency) && (
        <span
          className={cn(
            "text-muted-foreground",
            size === "md" ? "text-xs" : "text-[10px]",
          )}
        >
          {[name, country, currency].filter(Boolean).join(" · ") || "—"}
        </span>
      )}
    </span>
  );
}
