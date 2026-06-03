import { useQuery } from '@tanstack/react-query';
import { useParams } from '@tanstack/react-router';
import { apiFetch } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-keys';
import { AppShell } from '@/components/layout/app-shell';
import { MetricCard } from '@/components/shared/metric-card';
import { formatPercent } from '@/lib/utils';
import { useState } from 'react';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  AreaChart, Area, Legend,
} from 'recharts';
import type { BacktestDetail, BacktestMetrics } from '@/types/api';

const TABS = ['Summary', 'Equity', 'Trades', 'Audit'] as const;
const COLORS = ['#22c55e', '#3b82f6', '#a855f7', '#ef4444', '#f97316'];

export function BacktestResultsPage() {
  const { workspaceId, backtestId } = useParams({ strict: false }) as {
    workspaceId: string;
    backtestId: string;
  };
  const [tab, setTab] = useState<typeof TABS[number]>('Summary');

  const { data, isLoading } = useQuery({
    queryKey: queryKeys.backtests.detail(backtestId),
    queryFn: () => apiFetch<BacktestDetail>(`/api/workspaces/${workspaceId}/backtests/${backtestId}`),
    refetchInterval: (query) =>
      query.state.data?.run.status === 'running' || query.state.data?.run.status === 'queued'
        ? 3000
        : false,
  });

  if (isLoading) {
    return <AppShell><div className="text-sm text-muted-foreground">Loading...</div></AppShell>;
  }

  if (!data) {
    return <AppShell><div className="text-sm text-destructive">Backtest not found</div></AppShell>;
  }

  const { run, metrics } = data;
  const portfolioMetrics = metrics.find(m => m.source === 'portfolio');

  if (run.status === 'running' || run.status === 'queued') {
    return (
      <AppShell>
        <div className="flex items-center gap-3">
          <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-muted-foreground">Backtest {run.status}...</span>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-foreground">{run.name || 'Backtest Results'}</h2>
          <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${
            run.status === 'complete' ? 'bg-primary/10 text-primary' : 'bg-destructive/10 text-destructive'
          }`}>
            {run.status}
          </span>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 border-b border-border">
          {TABS.map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-3 py-1.5 text-xs font-medium border-b-2 transition-colors ${
                tab === t
                  ? 'border-primary text-foreground'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {tab === 'Summary' && portfolioMetrics && (
          <div className="grid grid-cols-4 gap-3">
            <MetricCard label="CAGR" value={formatPercent(portfolioMetrics.cagr)} />
            <MetricCard label="Volatility" value={formatPercent(portfolioMetrics.volatility)} />
            <MetricCard label="Sharpe" value={String(portfolioMetrics.sharpe_ratio?.toFixed(2) ?? '-')} />
            <MetricCard
              label="Max Drawdown"
              value={formatPercent(portfolioMetrics.max_drawdown)}
              negative
            />
            <MetricCard label="Sortino" value={String(portfolioMetrics.sortino_ratio?.toFixed(2) ?? '-')} />
            <MetricCard label="Calmar" value={String(portfolioMetrics.calmar_ratio?.toFixed(2) ?? '-')} />
            <MetricCard label="Win Rate" value={formatPercent(portfolioMetrics.win_rate)} />
            <MetricCard label="Total Return" value={formatPercent(portfolioMetrics.total_return)} />
          </div>
        )}

        {tab === 'Equity' && (
          <div className="space-y-4">
            <div className="bg-card border border-border rounded-md p-3">
              <ResponsiveContainer width="100%" height={400}>
                <LineChart>
                  {metrics.map((m, i) => {
                    if (!m.equity_curve) return null;
                    return (
                      <Line
                        key={m.source}
                        data={m.equity_curve}
                        dataKey="value"
                        name={m.source}
                        stroke={COLORS[i % COLORS.length]}
                        dot={false}
                        strokeWidth={m.source === 'portfolio' ? 2 : 1}
                      />
                    );
                  })}
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip
                    contentStyle={{ background: '#14161d', border: '1px solid #252830', fontSize: 11 }}
                    labelStyle={{ color: '#8b8f9a' }}
                  />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Drawdown chart */}
            {portfolioMetrics?.equity_curve && (
              <div className="bg-card border border-border rounded-md p-3">
                <div className="text-[10px] uppercase text-muted-foreground mb-2">Drawdown</div>
                <ResponsiveContainer width="100%" height={150}>
                  <AreaChart data={computeDrawdown(portfolioMetrics.equity_curve)}>
                    <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                    <YAxis tick={{ fontSize: 10 }} />
                    <Area
                      dataKey="drawdown"
                      stroke="#ef4444"
                      fill="#ef4444"
                      fillOpacity={0.15}
                    />
                    <Tooltip
                      contentStyle={{ background: '#14161d', border: '1px solid #252830', fontSize: 11 }}
                      formatter={(v: number) => [`${(v * 100).toFixed(2)}%`, 'Drawdown']}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        )}

        {tab === 'Trades' && (
          <div className="text-xs text-muted-foreground">
            Trades table — coming soon. Export via API: GET /api/workspaces/{workspaceId}/backtests/{backtestId}/export
          </div>
        )}

        {tab === 'Audit' && (
          <div className="text-xs text-muted-foreground">
            {portfolioMetrics?.warnings
              ? JSON.stringify(portfolioMetrics.warnings, null, 2)
              : 'No warnings recorded.'}
          </div>
        )}
      </div>
    </AppShell>
  );
}

function computeDrawdown(curve: Array<{ date: string; value: number }>) {
  let peak = curve[0]?.value ?? 0;
  return curve.map(({ date, value }) => {
    if (value > peak) peak = value;
    const drawdown = peak > 0 ? -(peak - value) / peak : 0;
    return { date, drawdown };
  });
}
