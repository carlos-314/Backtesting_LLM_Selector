/**
 * Showcase de los componentes base (Estrato 2).
 *
 * Esta ruta (`/__examples`) NO es UI de producto: es una galería interna
 * de los componentes con sus variantes y estados. Se monta sin guardián
 * para inspección rápida en desarrollo (no contiene datos del backend).
 *
 * NO es una pantalla de Storybook — es solo una tabla con cada componente
 * en cada estado relevante del mapa F3 §5.1.
 */
import * as React from "react";

import {
  ConfirmDialog,
  CursorPager,
  DataState,
  DataTable,
  EmptyState,
  ErrorState,
  FormField,
  PageHeader,
  type ColumnDef,
} from "@/components/base";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { toast } from "@/components/ui/toaster";
import { ApiError } from "@/lib/api-error";

export function ExamplesView() {
  return (
    <div className="container mx-auto max-w-5xl space-y-12 px-4 py-8">
      <PageHeader
        title="/__examples — galería de componentes base"
        description="Showcase interno de los componentes del Estrato 2 (F3 §4.2). No es UI de producto."
      />

      <Section title="PageHeader">
        <PageHeader
          title="Backtests"
          description="Subtítulo opcional"
          actions={
            <>
              <Button variant="outline" size="sm">Acción 2</Button>
              <Button size="sm">Acción 1</Button>
            </>
          }
        />
      </Section>

      <Section title="EmptyState">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <EmptyState title="Sin backtests todavía" />
          <EmptyState
            title="Sin selecciones"
            description="No hay semanas con runs resueltos en este periodo."
            action={{ label: "Ampliar rango", onAction: () => toast("Acción ejemplo") }}
          />
        </div>
      </Section>

      <Section title="ErrorState — códigos comunes">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <ErrorState
            error={new ApiError(500, "analysis_schema_mismatch", "Schema not matching")}
            onRetry={() => toast("Reintento")}
          />
          <ErrorState
            error={new ApiError(403, "user_not_authorized", "Not authorized")}
          />
          <ErrorState
            error={new ApiError(502, "analysis_unreachable", "Analysis DB down")}
            onRetry={() => toast("Reintento")}
          />
          <ErrorState
            error={new ApiError(409, "backtest_not_ready", "Not ready yet")}
          />
        </div>
      </Section>

      <Section title="DataState — cuatro caminos">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Sub label="loading">
            <DataState<{ items: string[] }> status="loading">{() => null}</DataState>
          </Sub>
          <Sub label="empty">
            <DataState<{ items: string[] }> status="empty">{() => null}</DataState>
          </Sub>
          <Sub label="error">
            <DataState<{ items: string[] }>
              status="error"
              error={new ApiError(502, "analysis_unreachable", "down")}
              onRetry={() => toast("retry")}
            >
              {() => null}
            </DataState>
          </Sub>
          <Sub label="ready (render-prop)">
            <DataState<{ items: string[] }>
              status="ready"
              data={{ items: ["AAPL", "MSFT", "GOOG"] }}
            >
              {(d) => (
                <ul className="text-sm">
                  {d.items.map((t) => (
                    <li key={t} className="rounded bg-muted px-2 py-1">{t}</li>
                  ))}
                </ul>
              )}
            </DataState>
          </Sub>
        </div>
      </Section>

      <Section title="FormField">
        <FormFieldExamples />
      </Section>

      <Section title="DataTable">
        <DataTableExamples />
      </Section>

      <Section title="CursorPager">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <Sub label="hasMore=true">
            <CursorPager hasMore onLoadMore={() => toast("loadMore")} />
          </Sub>
          <Sub label="isLoadingMore">
            <CursorPager hasMore isLoadingMore onLoadMore={() => undefined} />
          </Sub>
          <Sub label="hasMore=false (no se pinta)">
            <CursorPager hasMore={false} onLoadMore={() => undefined} />
            <span className="text-xs text-muted-foreground">(componente nulo)</span>
          </Sub>
        </div>
      </Section>

      <Section title="ConfirmDialog">
        <ConfirmDialogExamples />
      </Section>

      <Section title="Toasts (sonner)">
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={() => toast("Backtest en cola")}>
            toast (info)
          </Button>
          <Button variant="outline" size="sm" onClick={() => toast.success("Cancelado")}>
            toast.success
          </Button>
          <Button variant="outline" size="sm" onClick={() => toast.error("Conexión interrumpida")}>
            toast.error
          </Button>
        </div>
      </Section>

      <Section title="Badge variants">
        <div className="flex flex-wrap gap-2">
          <Badge>default</Badge>
          <Badge variant="secondary">secondary</Badge>
          <Badge variant="destructive">destructive</Badge>
          <Badge variant="outline">outline</Badge>
        </div>
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
      <Separator />
      <div className="pt-2">{children}</div>
    </section>
  );
}

function Sub({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="rounded-md border bg-card p-4">
      <div className="mb-2 text-xs uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      {children}
    </div>
  );
}

function FormFieldExamples() {
  const [name, setName] = React.useState("");
  const showError = name.trim().length > 0 && name.trim().length < 3;

  return (
    <div className="grid max-w-lg gap-4">
      <FormField label="Nombre" htmlFor="ex-name" hint="Mínimo 3 caracteres">
        <Input
          id="ex-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Nombre del backtest"
          aria-invalid={showError || undefined}
          aria-describedby={showError ? "ex-name-error" : "ex-name-hint"}
        />
      </FormField>
      <FormField
        label="Capital inicial"
        htmlFor="ex-cap"
        required
        error={showError ? "Tienes que dar un nombre de al menos 3 caracteres" : undefined}
      >
        <Input id="ex-cap" type="number" defaultValue="10000" />
      </FormField>
    </div>
  );
}

interface DemoRow {
  id: string;
  name: string;
  status: "pending" | "running" | "completed";
}

function DataTableExamples() {
  const columns: ColumnDef<DemoRow>[] = [
    { id: "name", header: "Nombre", cell: (r) => r.name },
    {
      id: "status",
      header: "Estado",
      cell: (r) => <Badge variant={r.status === "completed" ? "secondary" : "outline"}>{r.status}</Badge>,
    },
  ];
  const rows: DemoRow[] = [
    { id: "1", name: "BT semanal", status: "running" },
    { id: "2", name: "BT mensual", status: "completed" },
    { id: "3", name: "BT custom", status: "pending" },
  ];

  return (
    <div className="space-y-6">
      <Sub label="con filas">
        <DataTable<DemoRow>
          columns={columns}
          rows={rows}
          rowKey={(r) => r.id}
          onRowClick={(r) => toast(`click ${r.name}`)}
        />
      </Sub>
      <Sub label="loading inicial">
        <DataTable<DemoRow>
          columns={columns}
          rows={[]}
          rowKey={(r) => r.id}
          isLoading
        />
      </Sub>
      <Sub label="vacío">
        <DataTable<DemoRow> columns={columns} rows={[]} rowKey={(r) => r.id} />
      </Sub>
    </div>
  );
}

function ConfirmDialogExamples() {
  const [openA, setOpenA] = React.useState(false);
  const [openB, setOpenB] = React.useState(false);
  return (
    <div className="flex flex-wrap gap-2">
      <Button variant="outline" onClick={() => setOpenA(true)}>Abrir confirm (default)</Button>
      <Button variant="destructive" onClick={() => setOpenB(true)}>Abrir confirm (destructive)</Button>

      <ConfirmDialog
        open={openA}
        onOpenChange={setOpenA}
        title="¿Guardar cambios?"
        description="Se actualizará el registro."
        onConfirm={() => {
          toast.success("Guardado");
          setOpenA(false);
        }}
      />
      <ConfirmDialog
        open={openB}
        onOpenChange={setOpenB}
        title="¿Cancelar este backtest?"
        description="Esta acción no se puede deshacer."
        variant="destructive"
        confirmLabel="Sí, cancelar"
        onConfirm={() => {
          toast.success("Backtest cancelado");
          setOpenB(false);
        }}
      />
    </div>
  );
}
