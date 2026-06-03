import { useState } from 'react';
import { useParams, useNavigate } from '@tanstack/react-router';
import { useMutation, useQuery } from '@tanstack/react-query';
import { apiFetch } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-keys';
import { AppShell } from '@/components/layout/app-shell';
import type { SignalSummary, BacktestRun } from '@/types/api';

export function BacktestNewPage() {
  const { workspaceId } = useParams({ strict: false }) as { workspaceId: string };
  const navigate = useNavigate();

  const { data: weeks = [] } = useQuery({
    queryKey: queryKeys.signals.weeks(workspaceId),
    queryFn: () => apiFetch<SignalSummary[]>(`/api/workspaces/${workspaceId}/signals`),
  });

  const [config, setConfig] = useState({
    name: '',
    start_date: '',
    end_date: '',
    initial_capital: 100000,
    commission_pct: 0.001,
    slippage_bps: 5,
    rebalance_mode: 'composition',
    deduplicate: true,
    exclude_llm_errors: true,
    use_equal_weight_bench: true,
    use_random_bench: true,
    random_simulations: 1000,
    external_index_symbol: '',
  });

  const sortedWeeks = [...weeks].sort((a, b) => a.week_date.localeCompare(b.week_date));
  const minDate = sortedWeeks[0]?.week_date || '';
  const maxDate = sortedWeeks[sortedWeeks.length - 1]?.week_date || '';

  // Auto-fill dates on first load
  if (!config.start_date && minDate) {
    setConfig(c => ({ ...c, start_date: minDate, end_date: maxDate }));
  }

  const createMutation = useMutation({
    mutationFn: () =>
      apiFetch<BacktestRun>(`/api/workspaces/${workspaceId}/backtests`, {
        method: 'POST',
        body: JSON.stringify({
          ...config,
          external_index_symbol: config.external_index_symbol || null,
        }),
      }),
    onSuccess: (run) => {
      navigate({ to: `/workspaces/${workspaceId}/backtest/run/${run.id}` } as any);
    },
  });

  return (
    <AppShell>
      <div className="max-w-xl space-y-4">
        <h2 className="text-sm font-bold text-foreground">New Backtest</h2>

        {weeks.length === 0 && (
          <div className="text-xs text-muted-foreground bg-card border border-border rounded-md p-3">
            No signal data available. Upload weekly files first.
          </div>
        )}

        {/* Name */}
        <div>
          <label className="text-[10px] uppercase text-muted-foreground font-bold">Name (optional)</label>
          <input
            type="text"
            value={config.name}
            onChange={e => setConfig(c => ({ ...c, name: e.target.value }))}
            placeholder="e.g. Full range default config"
            className="w-full mt-1 bg-muted border border-border rounded-md px-3 py-1.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
          />
        </div>

        {/* Date range */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-[10px] uppercase text-muted-foreground font-bold">Start date</label>
            <input
              type="date"
              value={config.start_date}
              onChange={e => setConfig(c => ({ ...c, start_date: e.target.value }))}
              className="w-full mt-1 bg-muted border border-border rounded-md px-3 py-1.5 text-sm text-foreground focus:outline-none focus:border-primary"
            />
            <div className="text-[10px] text-muted-foreground mt-0.5">First signal: {minDate || '-'}</div>
          </div>
          <div>
            <label className="text-[10px] uppercase text-muted-foreground font-bold">End date</label>
            <input
              type="date"
              value={config.end_date}
              onChange={e => setConfig(c => ({ ...c, end_date: e.target.value }))}
              className="w-full mt-1 bg-muted border border-border rounded-md px-3 py-1.5 text-sm text-foreground focus:outline-none focus:border-primary"
            />
            <div className="text-[10px] text-muted-foreground mt-0.5">Last signal: {maxDate || '-'}</div>
          </div>
        </div>

        {/* Capital */}
        <div>
          <label className="text-[10px] uppercase text-muted-foreground font-bold">Initial capital (EUR)</label>
          <input
            type="number"
            value={config.initial_capital}
            onChange={e => setConfig(c => ({ ...c, initial_capital: Number(e.target.value) }))}
            className="w-full mt-1 bg-muted border border-border rounded-md px-3 py-1.5 text-sm text-foreground focus:outline-none focus:border-primary"
          />
        </div>

        {/* Costs */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-[10px] uppercase text-muted-foreground font-bold">Commission (%)</label>
            <input
              type="number"
              step="0.001"
              value={config.commission_pct}
              onChange={e => setConfig(c => ({ ...c, commission_pct: Number(e.target.value) }))}
              className="w-full mt-1 bg-muted border border-border rounded-md px-3 py-1.5 text-sm text-foreground focus:outline-none focus:border-primary"
            />
          </div>
          <div>
            <label className="text-[10px] uppercase text-muted-foreground font-bold">Slippage (bps)</label>
            <input
              type="number"
              step="1"
              value={config.slippage_bps}
              onChange={e => setConfig(c => ({ ...c, slippage_bps: Number(e.target.value) }))}
              className="w-full mt-1 bg-muted border border-border rounded-md px-3 py-1.5 text-sm text-foreground focus:outline-none focus:border-primary"
            />
          </div>
        </div>

        {/* Options */}
        <div className="space-y-2">
          <label className="text-[10px] uppercase text-muted-foreground font-bold">Options</label>
          <div className="space-y-1.5">
            {[
              { key: 'deduplicate', label: 'Deduplicate tickers in selection' },
              { key: 'exclude_llm_errors', label: 'Exclude LLM_ERROR tickers' },
            ].map(({ key, label }) => (
              <label key={key} className="flex items-center gap-2 text-xs text-foreground cursor-pointer">
                <input
                  type="checkbox"
                  checked={(config as any)[key]}
                  onChange={e => setConfig(c => ({ ...c, [key]: e.target.checked }))}
                  className="accent-primary"
                />
                {label}
              </label>
            ))}
          </div>
        </div>

        {/* Benchmarks */}
        <div className="space-y-2">
          <label className="text-[10px] uppercase text-muted-foreground font-bold">Benchmarks</label>
          <div className="space-y-1.5">
            <label className="flex items-center gap-2 text-xs text-foreground cursor-pointer">
              <input
                type="checkbox"
                checked={config.use_equal_weight_bench}
                onChange={e => setConfig(c => ({ ...c, use_equal_weight_bench: e.target.checked }))}
                className="accent-primary"
              />
              Equal-weight universe
            </label>
            <label className="flex items-center gap-2 text-xs text-foreground cursor-pointer">
              <input
                type="checkbox"
                checked={config.use_random_bench}
                onChange={e => setConfig(c => ({ ...c, use_random_bench: e.target.checked }))}
                className="accent-primary"
              />
              Random simulations
            </label>
            {config.use_random_bench && (
              <div className="ml-6">
                <input
                  type="number"
                  value={config.random_simulations}
                  onChange={e => setConfig(c => ({ ...c, random_simulations: Number(e.target.value) }))}
                  className="w-24 bg-muted border border-border rounded-md px-2 py-1 text-xs text-foreground focus:outline-none focus:border-primary"
                />
                <span className="text-[10px] text-muted-foreground ml-1">simulations</span>
              </div>
            )}
          </div>
          <div>
            <label className="text-[10px] uppercase text-muted-foreground font-bold">External index (optional)</label>
            <input
              type="text"
              value={config.external_index_symbol}
              onChange={e => setConfig(c => ({ ...c, external_index_symbol: e.target.value }))}
              placeholder="e.g. ^GSPC, ^STOXX50E"
              className="w-full mt-1 bg-muted border border-border rounded-md px-3 py-1.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
            />
          </div>
        </div>

        {/* Submit */}
        {createMutation.isError && (
          <div className="bg-destructive/10 border border-destructive/30 text-destructive text-xs rounded-md p-2">
            {(createMutation.error as any)?.message || 'Failed to create backtest'}
          </div>
        )}

        <button
          onClick={() => createMutation.mutate()}
          disabled={!config.start_date || !config.end_date || createMutation.isPending || weeks.length === 0}
          className="w-full px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          {createMutation.isPending ? 'Launching...' : 'Launch Backtest'}
        </button>
      </div>
    </AppShell>
  );
}
