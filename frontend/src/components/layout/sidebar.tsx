import { useNavigate, useParams } from '@tanstack/react-router';

const NAV_ITEMS = [
  { label: 'Dashboard', path: '', icon: 'H' },
  { label: 'Upload', path: '/upload', icon: 'U' },
  { label: 'Signals', path: '/signals', icon: 'S' },
  { label: 'Backtests', path: '/backtest/new', icon: 'B' },
  { label: 'Settings', path: '/settings', icon: 'G' },
];

export function Sidebar() {
  const navigate = useNavigate();
  const { workspaceId } = useParams({ strict: false }) as { workspaceId?: string };

  return (
    <aside className="w-56 shrink-0 border-r border-border bg-card min-h-screen flex flex-col">
      <div className="p-4 border-b border-border">
        <h1 className="text-sm font-bold text-foreground tracking-tight">LLM Backtester</h1>
      </div>

      <nav className="flex-1 p-2 space-y-0.5">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.path}
            onClick={() => {
              if (workspaceId) {
                navigate({ to: `/workspaces/${workspaceId}${item.path}` } as any);
              }
            }}
            className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground hover:bg-accent rounded-md transition-colors text-left"
          >
            <span className="w-5 h-5 flex items-center justify-center bg-muted rounded text-[10px] font-mono font-bold">
              {item.icon}
            </span>
            {item.label}
          </button>
        ))}
      </nav>
    </aside>
  );
}
