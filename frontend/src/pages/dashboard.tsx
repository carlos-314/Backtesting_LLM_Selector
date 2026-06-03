import { useQuery } from '@tanstack/react-query';
import { useParams } from '@tanstack/react-router';
import { apiFetch } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-keys';
import { AppShell } from '@/components/layout/app-shell';
import { MetricCard } from '@/components/shared/metric-card';
import type { SignalSummary, UploadBatch } from '@/types/api';

export function DashboardPage() {
  const { workspaceId } = useParams({ strict: false }) as { workspaceId: string };

  const { data: uploads = [] } = useQuery({
    queryKey: queryKeys.uploads.all(workspaceId),
    queryFn: () => apiFetch<UploadBatch[]>(`/api/workspaces/${workspaceId}/uploads`),
  });

  const { data: signalWeeks = [] } = useQuery({
    queryKey: queryKeys.signals.weeks(workspaceId),
    queryFn: () => apiFetch<SignalSummary[]>(`/api/workspaces/${workspaceId}/signals`),
  });

  return (
    <AppShell>
      <div className="space-y-4">
        <h2 className="text-sm font-bold text-foreground">Dashboard</h2>

        <div className="grid grid-cols-4 gap-3">
          <MetricCard label="Weeks loaded" value={String(uploads.filter(u => u.status === 'complete').length)} />
          <MetricCard label="Total tickers" value={String(new Set(signalWeeks.flatMap(() => [])).size || '-')} />
          <MetricCard label="Latest week" value={signalWeeks[0]?.week_date || '-'} />
          <MetricCard label="Pending uploads" value={String(uploads.filter(u => u.status === 'pending').length)} />
        </div>

        <div className="bg-card border border-border rounded-md">
          <div className="p-3 border-b border-border">
            <h3 className="text-xs font-bold text-foreground">Recent uploads</h3>
          </div>
          <div className="divide-y divide-border">
            {uploads.slice(0, 10).map((u) => (
              <div key={u.id} className="px-3 py-2 flex items-center justify-between text-xs">
                <span className="text-foreground font-mono">{u.week_date}</span>
                <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                  u.status === 'complete' ? 'bg-primary/10 text-primary' :
                  u.status === 'error' ? 'bg-destructive/10 text-destructive' :
                  'bg-muted text-muted-foreground'
                }`}>
                  {u.status}
                </span>
              </div>
            ))}
            {uploads.length === 0 && (
              <div className="px-3 py-4 text-xs text-muted-foreground text-center">
                No uploads yet. Go to Upload to add your first weekly files.
              </div>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
