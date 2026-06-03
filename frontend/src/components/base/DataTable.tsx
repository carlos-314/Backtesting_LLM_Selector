/**
 * `DataTable<T>` — tabla genérica controlada (F3 §4.2).
 *
 * NO pagina ni ordena por su cuenta: recibe `rows` ya cargadas y emite
 * `onSortChange`. El orden y la página son decisiones de servidor (cursor
 * opaco, F2 §6.1).
 *
 * Sirve para la lista de backtests (F3 §1.3). **No para la matriz**
 * (`SelectionMatrix` es un componente de dominio propio, F3 §3.3).
 *
 * Decisiones (F3 §4.2):
 *  - Genérico en `<T>`: no sabe nada del dominio.
 *  - Controlado: estados (sort, hover) viven en el caller.
 *  - Eventos `on*` reciben el dato ya útil (la fila), no el evento DOM crudo.
 *  - F3 §4.2 I4: la columna se ordena solo si `sortable === true`. La lista
 *    de backtests día uno NO ordena (cursor solo por recencia).
 *
 * Ejemplo:
 * ```tsx
 * type Row = { id: string; name: string; status: string };
 * const columns: ColumnDef<Row>[] = [
 *   { id: "name", header: "Nombre", cell: (r) => r.name },
 *   { id: "status", header: "Estado", cell: (r) => <BacktestStatusBadge status={r.status} /> },
 * ];
 * <DataTable columns={columns} rows={rows} rowKey={(r) => r.id} onRowClick={...} />
 * ```
 */
import * as React from "react";
import { ArrowDown, ArrowUp } from "lucide-react";

import { EmptyState } from "@/components/base/EmptyState";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

export interface ColumnDef<T> {
  id: string;
  header: React.ReactNode;
  cell: (row: T) => React.ReactNode;
  sortable?: boolean;
  align?: "start" | "end";
  width?: string;
}

export interface SortState {
  columnId: string;
  direction: "asc" | "desc";
}

export interface DataTableProps<T> {
  columns: ColumnDef<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  onRowClick?: (row: T) => void;
  sort?: SortState;
  onSortChange?: (sort: SortState) => void;
  isLoading?: boolean;
  /** Render alternativo cuando `rows` está vacío y `isLoading` es false. */
  emptySlot?: React.ReactNode;
  caption?: string;
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  onRowClick,
  sort,
  onSortChange,
  isLoading,
  emptySlot,
  caption,
}: DataTableProps<T>) {
  const handleHeaderClick = (col: ColumnDef<T>) => {
    if (!col.sortable || !onSortChange) return;
    const direction: "asc" | "desc" =
      sort?.columnId === col.id && sort.direction === "asc" ? "desc" : "asc";
    onSortChange({ columnId: col.id, direction });
  };

  return (
    <Table>
      {caption && <caption className="sr-only">{caption}</caption>}
      <TableHeader>
        <TableRow>
          {columns.map((col) => {
            const isActive = sort?.columnId === col.id;
            const sortable = col.sortable && onSortChange;
            return (
              <TableHead
                key={col.id}
                style={{ width: col.width, textAlign: col.align === "end" ? "right" : "left" }}
                aria-sort={
                  sortable
                    ? isActive
                      ? sort?.direction === "asc"
                        ? "ascending"
                        : "descending"
                      : "none"
                    : undefined
                }
              >
                {sortable ? (
                  <button
                    type="button"
                    onClick={() => handleHeaderClick(col)}
                    className="inline-flex items-center gap-1 hover:text-foreground"
                  >
                    {col.header}
                    {isActive ? (
                      sort?.direction === "asc" ? (
                        <ArrowUp className="h-3 w-3" aria-hidden="true" />
                      ) : (
                        <ArrowDown className="h-3 w-3" aria-hidden="true" />
                      )
                    ) : null}
                  </button>
                ) : (
                  col.header
                )}
              </TableHead>
            );
          })}
        </TableRow>
      </TableHeader>
      <TableBody>
        {isLoading && rows.length === 0 ? (
          // Loading inicial → 3 filas skeleton
          Array.from({ length: 3 }).map((_, i) => (
            <TableRow key={`skel-${i}`}>
              {columns.map((col) => (
                <TableCell key={col.id}>
                  <Skeleton className="h-4 w-3/4" />
                </TableCell>
              ))}
            </TableRow>
          ))
        ) : rows.length === 0 ? (
          <TableRow>
            <TableCell colSpan={columns.length} className="p-0">
              {emptySlot ?? <EmptyState title="Sin resultados" />}
            </TableCell>
          </TableRow>
        ) : (
          rows.map((row) => (
            <TableRow
              key={rowKey(row)}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              className={cn(onRowClick && "cursor-pointer")}
              role={onRowClick ? "button" : undefined}
              tabIndex={onRowClick ? 0 : undefined}
              onKeyDown={
                onRowClick
                  ? (e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        onRowClick(row);
                      }
                    }
                  : undefined
              }
            >
              {columns.map((col) => (
                <TableCell
                  key={col.id}
                  style={{ textAlign: col.align === "end" ? "right" : "left" }}
                >
                  {col.cell(row)}
                </TableCell>
              ))}
            </TableRow>
          ))
        )}
      </TableBody>
    </Table>
  );
}
