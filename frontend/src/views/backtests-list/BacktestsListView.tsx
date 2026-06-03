/**
 * V-BT-LISTA — Lista de backtests (F3 §1.3, §5.3, §4.2 I4).
 *
 * F3 §4.2 I4: sin orden por columna día uno (cursor opaco solo da recencia).
 */
import { Link, useNavigate } from "@tanstack/react-router";
import * as React from "react";

import { CursorPager } from "@/components/base/CursorPager";
import { DataState } from "@/components/base/DataState";
import { DataTable, type ColumnDef } from "@/components/base/DataTable";
import { EmptyState } from "@/components/base/EmptyState";
import { PageHeader } from "@/components/base/PageHeader";
import { Button } from "@/components/ui/button";
import { BacktestStatusBadge } from "@/domain/backtesting/BacktestStatusBadge";
import { RoleGate } from "@/domain/screening/RoleGate";
import {
  useBacktestsListQuery,
  type BacktestSummary,
} from "@/lib/queries/backtests";

export function BacktestsListView() {
  const navigate = useNavigate();
  const [pages, setPages] = React.useState<
    { items: BacktestSummary[]; next_cursor: string | null }[]
  >([]);
  const [cursor, setCursor] = React.useState<string | null>(null);
  const query = useBacktestsListQuery({ cursor });

  React.useEffect(() => {
    if (query.data) {
      if (cursor === null) {
        setPages([query.data]);
      } else if (pages[pages.length - 1] !== query.data) {
        setPages((p) => [...p, query.data!]);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query.data]);

  const allItems: BacktestSummary[] = pages.flatMap((p) => p.items);
  const nextCursor = pages.length > 0 ? pages[pages.length - 1].next_cursor : null;

  const columns: ColumnDef<BacktestSummary>[] = [
    {
      id: "name",
      header: "Nombre",
      cell: (r) => <span className="font-medium">{r.name}</span>,
    },
    {
      id: "status",
      header: "Estado",
      cell: (r) => <BacktestStatusBadge status={r.status} />,
    },
    {
      id: "created_at",
      header: "Creado",
      cell: (r) => (
        <time className="text-xs text-muted-foreground" dateTime={r.created_at}>
          {new Date(r.created_at).toLocaleString("es-ES")}
        </time>
      ),
      align: "end",
    },
  ];

  const status =
    pages.length === 0 && query.isLoading
      ? "loading"
      : query.error
        ? "error"
        : allItems.length === 0 && !query.isLoading
          ? "empty"
          : "ready";

  return (
    <>
      <PageHeader
        title="Backtests"
        actions={
          <RoleGate allow={["analyst", "admin"]}>
            <Button asChild>
              <Link to="/backtests/nuevo">Lanzar backtest</Link>
            </Button>
          </RoleGate>
        }
      />
      <DataState<{ items: BacktestSummary[]; next_cursor: string | null }>
        status={status}
        data={{ items: allItems, next_cursor: nextCursor }}
        error={query.error ?? undefined}
        onRetry={() => void query.refetch()}
        emptySlot={
          <EmptyState
            title="Sin backtests todavía"
            description="Lanza el primero desde el botón superior."
          />
        }
      >
        {(data) => (
          <div className="space-y-3">
            <DataTable
              columns={columns}
              rows={data.items}
              rowKey={(r) => r.id}
              onRowClick={(r) =>
                void navigate({ to: "/backtests/$id", params: { id: r.id } })
              }
            />
            <CursorPager
              hasMore={!!data.next_cursor}
              isLoadingMore={query.isFetching && cursor !== null}
              onLoadMore={() => setCursor(data.next_cursor)}
            />
          </div>
        )}
      </DataState>
    </>
  );
}
