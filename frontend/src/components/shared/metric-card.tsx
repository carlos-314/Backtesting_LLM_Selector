interface MetricCardProps {
  label: string;
  value: string;
  subtitle?: string;
  negative?: boolean;
}

export function MetricCard({ label, value, subtitle, negative }: MetricCardProps) {
  return (
    <div className="bg-card border border-border rounded-md p-3">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">{label}</div>
      <div className={`text-lg font-mono font-bold ${negative ? 'text-destructive' : 'text-foreground'}`}>
        {value}
      </div>
      {subtitle && <div className="text-[10px] text-muted-foreground mt-0.5">{subtitle}</div>}
    </div>
  );
}
