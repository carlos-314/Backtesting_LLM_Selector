import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from '@tanstack/react-router';
import { apiFetch } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-keys';
import { useState } from 'react';
import type { Workspace } from '@/types/api';

export function WorkspacesPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [newName, setNewName] = useState('');

  const { data: workspaces = [], isLoading } = useQuery({
    queryKey: queryKeys.workspaces.all,
    queryFn: () => apiFetch<Workspace[]>('/api/workspaces'),
  });

  const createMutation = useMutation({
    mutationFn: (name: string) =>
      apiFetch<Workspace>('/api/workspaces', {
        method: 'POST',
        body: JSON.stringify({ name }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.workspaces.all });
      setNewName('');
    },
  });

  if (isLoading) {
    return <div className="p-8 text-sm text-muted-foreground">Loading...</div>;
  }

  return (
    <div className="min-h-screen bg-background p-8">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-lg font-bold text-foreground mb-4">Workspaces</h1>

        <div className="space-y-2 mb-6">
          {workspaces.map((ws) => (
            <button
              key={ws.id}
              onClick={() => navigate({ to: `/workspaces/${ws.id}` } as any)}
              className="w-full flex items-center justify-between bg-card border border-border rounded-md p-3 hover:border-primary/50 transition-colors text-left"
            >
              <div>
                <div className="text-sm font-medium text-foreground">{ws.name}</div>
                <div className="text-[10px] text-muted-foreground">{ws.slug}</div>
              </div>
              <div className="text-[10px] text-muted-foreground">
                {new Date(ws.created_at).toLocaleDateString()}
              </div>
            </button>
          ))}
        </div>

        <div className="flex gap-2">
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="New workspace name"
            className="flex-1 bg-muted border border-border rounded-md px-3 py-1.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
          />
          <button
            onClick={() => newName && createMutation.mutate(newName)}
            disabled={!newName || createMutation.isPending}
            className="px-4 py-1.5 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
          >
            Create
          </button>
        </div>
      </div>
    </div>
  );
}
