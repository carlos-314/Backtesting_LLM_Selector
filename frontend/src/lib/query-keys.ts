export const queryKeys = {
  auth: {
    me: ['auth', 'me'] as const,
  },
  workspaces: {
    all: ['workspaces'] as const,
    detail: (id: string) => ['workspaces', id] as const,
    members: (id: string) => ['workspaces', id, 'members'] as const,
  },
  uploads: {
    all: (wsId: string) => ['uploads', wsId] as const,
    detail: (wsId: string, id: string) => ['uploads', wsId, id] as const,
  },
  signals: {
    weeks: (wsId: string) => ['signals', 'weeks', wsId] as const,
    heatmap: (wsId: string) => ['signals', 'heatmap', wsId] as const,
    weekDetail: (wsId: string, weekDate: string) => ['signals', 'week', wsId, weekDate] as const,
    dossier: (wsId: string, weekDate: string, ticker: string) =>
      ['signals', 'dossier', wsId, weekDate, ticker] as const,
  },
  backtests: {
    all: (wsId: string) => ['backtests', wsId] as const,
    detail: (btId: string) => ['backtests', 'detail', btId] as const,
    compare: (ids: string[]) => ['backtests', 'compare', ...ids] as const,
  },
  jobs: {
    detail: (jobId: string) => ['jobs', jobId] as const,
  },
} as const;
