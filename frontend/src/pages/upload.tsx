import { useState, useCallback } from 'react';
import { useParams } from '@tanstack/react-router';
import { useQueryClient } from '@tanstack/react-query';
import { apiUpload } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-keys';
import { AppShell } from '@/components/layout/app-shell';

interface FilePair {
  date: string;
  xlsx: File | null;
  txt: File | null;
  status: 'incomplete' | 'ready' | 'uploading' | 'done' | 'error';
  progress: number;
  error?: string;
}

function extractDate(filename: string): string | null {
  const match = filename.match(/(\d{8})/);
  return match ? match[1] : null;
}

export function UploadPage() {
  const { workspaceId } = useParams({ strict: false }) as { workspaceId: string };
  const queryClient = useQueryClient();
  const [pairs, setPairs] = useState<Map<string, FilePair>>(new Map());

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const files = Array.from(e.dataTransfer.files);
    addFiles(files);
  }, []);

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      addFiles(Array.from(e.target.files));
    }
  }, []);

  const addFiles = (files: File[]) => {
    setPairs(prev => {
      const next = new Map(prev);
      for (const file of files) {
        const date = extractDate(file.name);
        if (!date) continue;

        const existing = next.get(date) || { date, xlsx: null, txt: null, status: 'incomplete' as const, progress: 0 };

        if (file.name.endsWith('.xlsx')) existing.xlsx = file;
        else if (file.name.endsWith('.txt')) existing.txt = file;
        else continue;

        existing.status = existing.xlsx && existing.txt ? 'ready' : 'incomplete';
        next.set(date, existing);
      }
      return next;
    });
  };

  const uploadAll = async () => {
    const readyPairs = Array.from(pairs.entries()).filter(([, p]) => p.status === 'ready');

    for (const [date, pair] of readyPairs) {
      setPairs(prev => {
        const next = new Map(prev);
        next.set(date, { ...pair, status: 'uploading', progress: 0 });
        return next;
      });

      try {
        const formData = new FormData();
        formData.append('xlsx_file', pair.xlsx!);
        formData.append('txt_file', pair.txt!);

        await apiUpload(
          `/api/workspaces/${workspaceId}/uploads`,
          formData,
          (progress) => {
            setPairs(prev => {
              const next = new Map(prev);
              const p = next.get(date)!;
              next.set(date, { ...p, progress });
              return next;
            });
          },
        );

        setPairs(prev => {
          const next = new Map(prev);
          next.set(date, { ...pair, status: 'done', progress: 100 });
          return next;
        });
      } catch (err: any) {
        setPairs(prev => {
          const next = new Map(prev);
          next.set(date, { ...pair, status: 'error', error: err.message });
          return next;
        });
      }
    }

    queryClient.invalidateQueries({ queryKey: queryKeys.uploads.all(workspaceId) });
    queryClient.invalidateQueries({ queryKey: queryKeys.signals.weeks(workspaceId) });
  };

  const readyCount = Array.from(pairs.values()).filter(p => p.status === 'ready').length;

  return (
    <AppShell>
      <div className="space-y-4 max-w-2xl">
        <h2 className="text-sm font-bold text-foreground">Upload weekly files</h2>

        <div
          onDrop={handleDrop}
          onDragOver={(e) => e.preventDefault()}
          className="border-2 border-dashed border-border rounded-md p-8 text-center hover:border-primary/50 transition-colors"
        >
          <p className="text-sm text-muted-foreground mb-2">
            Drop .xlsx and .txt files here
          </p>
          <p className="text-[10px] text-muted-foreground mb-3">
            Files are paired by date (YYYYMMDD) in the filename
          </p>
          <label className="inline-block px-3 py-1.5 bg-muted rounded-md text-xs text-foreground cursor-pointer hover:bg-accent transition-colors">
            Browse files
            <input type="file" multiple accept=".xlsx,.txt" onChange={handleFileInput} className="hidden" />
          </label>
        </div>

        {pairs.size > 0 && (
          <div className="bg-card border border-border rounded-md">
            <div className="p-3 border-b border-border flex items-center justify-between">
              <h3 className="text-xs font-bold text-foreground">File pairs</h3>
              <button
                onClick={uploadAll}
                disabled={readyCount === 0}
                className="px-3 py-1 bg-primary text-primary-foreground rounded text-xs font-medium hover:bg-primary/90 disabled:opacity-50"
              >
                Upload {readyCount} pair{readyCount !== 1 ? 's' : ''}
              </button>
            </div>
            <div className="divide-y divide-border">
              {Array.from(pairs.entries())
                .sort(([a], [b]) => b.localeCompare(a))
                .map(([date, pair]) => (
                  <div key={date} className="px-3 py-2 flex items-center gap-3 text-xs">
                    <span className="font-mono text-foreground w-20">{date}</span>
                    <span className={pair.xlsx ? 'text-primary' : 'text-muted-foreground'}>
                      {pair.xlsx ? pair.xlsx.name : 'missing .xlsx'}
                    </span>
                    <span className={pair.txt ? 'text-primary' : 'text-muted-foreground'}>
                      {pair.txt ? pair.txt.name : 'missing .txt'}
                    </span>
                    <span className="ml-auto">
                      {pair.status === 'uploading' && (
                        <span className="text-muted-foreground">{pair.progress}%</span>
                      )}
                      {pair.status === 'done' && <span className="text-primary">Done</span>}
                      {pair.status === 'error' && (
                        <span className="text-destructive" title={pair.error}>Error</span>
                      )}
                      {pair.status === 'ready' && <span className="text-primary">Ready</span>}
                      {pair.status === 'incomplete' && (
                        <span className="text-muted-foreground">Incomplete</span>
                      )}
                    </span>
                  </div>
                ))}
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
