import { useQuery } from '@tanstack/react-query';
import { useParams } from '@tanstack/react-router';
import { apiFetch } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-keys';
import { AppShell } from '@/components/layout/app-shell';
import { useState } from 'react';
import type { HeatmapData, DossierData } from '@/types/api';

const CELL_W = 80;
const CELL_H = 26;
const LABEL_WIDTH = 240;
const HEADER_HEIGHT = 32;

export function SignalsPage() {
  const { workspaceId } = useParams({ strict: false }) as { workspaceId: string };
  const [selectedCell, setSelectedCell] = useState<{ ticker: string; week: string } | null>(null);

  const { data: heatmap, isLoading } = useQuery({
    queryKey: queryKeys.signals.heatmap(workspaceId),
    queryFn: () => apiFetch<HeatmapData>(`/api/workspaces/${workspaceId}/signals/heatmap`),
  });

  const { data: dossier } = useQuery({
    queryKey: queryKeys.signals.dossier(workspaceId, selectedCell?.week || '', selectedCell?.ticker || ''),
    queryFn: () =>
      apiFetch<DossierData>(
        `/api/workspaces/${workspaceId}/signals/${selectedCell!.week}/${selectedCell!.ticker}`,
      ),
    enabled: !!selectedCell,
  });

  if (isLoading) {
    return <AppShell><div className="text-sm text-muted-foreground">Loading signals...</div></AppShell>;
  }

  if (!heatmap || heatmap.tickers.length === 0) {
    return (
      <AppShell>
        <div className="text-sm text-muted-foreground">
          No signals yet. Upload weekly files first.
        </div>
      </AppShell>
    );
  }

  const cellMap = new Map<string, { in_universe: boolean; is_selected: boolean }>();
  for (const cell of heatmap.cells) {
    cellMap.set(`${cell.ticker}-${cell.week_date}`, cell);
  }

  return (
    <AppShell>
      <div className="flex gap-4">
        <div className="flex-1 overflow-auto">
          <h2 className="text-sm font-bold text-foreground mb-3">Signal Heatmap</h2>

          {/* HTML table-based heatmap for proper text rendering */}
          <div className="inline-block">
            <table className="border-collapse font-mono text-[10px]">
              <thead>
                <tr>
                  <th className="text-left px-1 py-1 w-[50px] text-foreground">Ticker</th>
                  <th className="text-left px-1 py-1 text-muted-foreground font-normal" style={{ minWidth: 140 }}>Company</th>
                  <th className="text-right px-1 py-1 w-[30px] text-muted-foreground font-normal">Sel</th>
                  {heatmap.weeks.map((week) => (
                    <th key={week} className="text-center px-0.5 py-1 text-muted-foreground font-normal whitespace-nowrap">
                      {week}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {heatmap.tickers.map((tickerInfo) => (
                  <tr key={tickerInfo.symbol} className="hover:bg-muted/30">
                    <td className="px-1 py-0.5 font-bold text-foreground whitespace-nowrap">
                      {tickerInfo.symbol}
                    </td>
                    <td className="px-1 py-0.5 text-muted-foreground whitespace-nowrap overflow-hidden max-w-[160px]" style={{ textOverflow: 'ellipsis' }}>
                      {tickerInfo.name || ''}
                    </td>
                    <td className="px-1 py-0.5 text-right text-primary font-bold">
                      {tickerInfo.selection_count > 0 ? `${tickerInfo.selection_count}x` : ''}
                    </td>
                    {heatmap.weeks.map((week) => {
                      const cell = cellMap.get(`${tickerInfo.symbol}-${week}`);
                      let bg = 'bg-zinc-900/50';
                      let border = '';
                      if (cell?.is_selected) {
                        bg = 'bg-emerald-500';
                      } else if (cell?.in_universe) {
                        bg = 'bg-blue-600/30';
                      }
                      if (selectedCell?.ticker === tickerInfo.symbol && selectedCell?.week === week) {
                        border = 'ring-1 ring-foreground';
                      }

                      return (
                        <td key={`${tickerInfo.symbol}-${week}`} className="px-0.5 py-0.5">
                          <div
                            className={`w-[68px] h-[20px] rounded-sm cursor-pointer hover:opacity-80 ${bg} ${border}`}
                            onClick={() =>
                              cell?.in_universe &&
                              setSelectedCell({ ticker: tickerInfo.symbol, week })
                            }
                          />
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Dossier side panel */}
        {selectedCell && (
          <div className="w-96 shrink-0 bg-card border border-border rounded-md overflow-y-auto max-h-[calc(100vh-8rem)]">
            <div className="p-3 border-b border-border flex items-center justify-between">
              <div>
                <span className="text-sm font-bold text-foreground font-mono">{selectedCell.ticker}</span>
                <span className="text-[10px] text-muted-foreground ml-2">{selectedCell.week}</span>
              </div>
              <button
                onClick={() => setSelectedCell(null)}
                className="text-muted-foreground hover:text-foreground text-sm"
              >
                X
              </button>
            </div>

            {dossier ? (
              <div className="p-3 space-y-3 text-xs text-foreground">
                {dossier.role_activity && (
                  <div>
                    <div className="text-[10px] uppercase text-primary font-bold mb-0.5">Selected</div>
                    <div className="text-muted-foreground">{dossier.role_activity}</div>
                  </div>
                )}
                {dossier.justification && (
                  <div>
                    <div className="text-[10px] uppercase text-muted-foreground font-bold mb-0.5">Justification</div>
                    <div>{dossier.justification}</div>
                  </div>
                )}
                {[
                  ['Growth Profile', dossier.growth_profile],
                  ['Margins & Efficiency', dossier.margins_efficiency],
                  ['Financial Health', dossier.financial_health],
                  ['Relative Valuation', dossier.relative_valuation],
                  ['Management Quality', dossier.management_quality],
                  ['Main Risks', dossier.main_risks],
                  ['Key Opportunities', dossier.key_opportunities],
                  ['General Conclusion', dossier.general_conclusion],
                ].map(([label, text]) =>
                  text ? (
                    <div key={label as string}>
                      <div className="text-[10px] uppercase text-muted-foreground font-bold mb-0.5">{label}</div>
                      <div className="whitespace-pre-wrap">{text}</div>
                    </div>
                  ) : null,
                )}

                {dossier.signal && (
                  <div>
                    <div className="text-[10px] uppercase text-muted-foreground font-bold mb-1">Metrics</div>
                    <div className="grid grid-cols-2 gap-1 font-mono text-[10px]">
                      {dossier.signal.cagr_pot != null && <div>CAGR Pot: {dossier.signal.cagr_pot}</div>}
                      {dossier.signal.mod1y_per != null && <div>PER: {dossier.signal.mod1y_per}</div>}
                      {dossier.signal.mod1y_ev_ebitda != null && <div>EV/EBITDA: {dossier.signal.mod1y_ev_ebitda}</div>}
                      {dossier.signal.mod1y_p_fcf != null && <div>P/FCF: {dossier.signal.mod1y_p_fcf}</div>}
                      {dossier.signal.perfil_compounder && <div>Profile: {dossier.signal.perfil_compounder}</div>}
                      {dossier.signal.estado_perf_vs_ev && <div>Valuation: {dossier.signal.estado_perf_vs_ev}</div>}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="p-3 text-xs text-muted-foreground">Loading dossier...</div>
            )}
          </div>
        )}
      </div>
    </AppShell>
  );
}
