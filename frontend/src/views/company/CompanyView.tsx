/**
 * V-COMPANY — Ficha de empresa en una semana (F3 §1.3, §5.3).
 *
 * El catálogo definitivo de campos está pendiente de ADR-0002; día uno
 * usamos shape mínimo + bloques JSONB raw.
 */
import { Link, useParams } from "@tanstack/react-router";

import { DataState } from "@/components/base/DataState";
import { PageHeader } from "@/components/base/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CompanyMetrics } from "@/domain/screening/CompanyMetrics";
import { CompanyQualitative } from "@/domain/screening/CompanyQualitative";
import { TickerLabel } from "@/domain/screening/TickerLabel";
import { useCompanyQuery } from "@/lib/queries/screening";

export function CompanyView() {
  const { semana, ticker } = useParams({ strict: false }) as {
    semana?: string;
    ticker?: string;
  };
  const query = useCompanyQuery(semana, ticker);

  const status =
    query.isLoading
      ? "loading"
      : query.error
        ? "error"
        : "ready";

  return (
    <>
      <Button asChild variant="ghost" size="sm" className="mb-2">
        <Link to="/mapa">← Volver al mapa</Link>
      </Button>
      <DataState
        status={status}
        data={query.data}
        error={query.error ?? undefined}
        onRetry={() => void query.refetch()}
      >
        {(data) => (
          <div className="space-y-6">
            <PageHeader
              title=""
              actions={
                <div className="flex items-center gap-2">
                  {data.in_portfolio ? (
                    <Badge variant="default">Seleccionada</Badge>
                  ) : (
                    <Badge variant="outline">En universo</Badge>
                  )}
                </div>
              }
            />
            <div className="-mt-12 flex items-end justify-between gap-4">
              <TickerLabel
                ticker={data.ticker}
                name={data.name}
                country={data.country}
                currency={data.currency}
              />
              <div className="text-xs text-muted-foreground">
                Semana <span className="font-mono">{data.week_date}</span> · Run{" "}
                <span className="font-mono">{data.run_code}</span>
              </div>
            </div>

            <Tabs defaultValue="metrics">
              <TabsList>
                <TabsTrigger value="metrics">Métricas</TabsTrigger>
                <TabsTrigger value="qualitative">Análisis LLM</TabsTrigger>
              </TabsList>
              <TabsContent value="metrics" className="pt-4">
                <CompanyMetrics raw={data.raw_processed_stock} />
              </TabsContent>
              <TabsContent value="qualitative" className="pt-4">
                <CompanyQualitative raw={data.raw_processed_stock} />
              </TabsContent>
            </Tabs>
          </div>
        )}
      </DataState>
    </>
  );
}
