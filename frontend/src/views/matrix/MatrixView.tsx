/**
 * V-MATRIX — Mapa histórico (F3 §1.3, §5.3, §6.1 I3).
 *
 * Ventana de semanas (`from`/`to`) parametriza la petición y vive en la
 * vista (F3 §6.1 I3). Filtros y orden son cliente-side sobre los datos
 * ya cargados — no tocan ADR-0001.
 *
 * Orden por defecto (a petición de producto):
 *   1. nº de veces seleccionada DESC
 *   2. ticker ASC (desempate)
 *
 * Filtros día uno (en cliente):
 *   - búsqueda por ticker o nombre
 *   - "solo seleccionadas" (al menos 1 selección en la ventana)
 *   - por país
 */
import * as React from "react";
import { Search, X } from "lucide-react";

import { DataState } from "@/components/base/DataState";
import { PageHeader } from "@/components/base/PageHeader";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { SelectionMatrix } from "@/domain/screening/SelectionMatrix";
import { useMatrixQuery } from "@/lib/queries/screening";

const ALL_COUNTRIES = "__all__";

function monday(d: Date): Date {
  const out = new Date(d);
  out.setDate(out.getDate() - ((out.getDay() + 6) % 7));
  return out;
}
function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}
function addWeeks(d: Date, n: number): Date {
  const out = new Date(d);
  out.setDate(out.getDate() + n * 7);
  return out;
}

export function MatrixView() {
  const [windowWeeks, setWindowWeeks] = React.useState(26);
  const [search, setSearch] = React.useState("");
  const [onlySelected, setOnlySelected] = React.useState(false);
  const [country, setCountry] = React.useState<string>(ALL_COUNTRIES);

  const today = React.useMemo(() => monday(new Date()), []);
  const to = isoDate(today);
  const from = isoDate(addWeeks(today, -(windowWeeks - 1)));

  const query = useMatrixQuery({ from, to });

  // selected_count por ticker (sobre toda la matriz cargada, no sobre los filtros)
  const selectedCounts = React.useMemo(() => {
    const m = new Map<string, number>();
    if (!query.data) return m;
    for (const c of query.data.cells) {
      if (c.state === "selected") {
        m.set(c.ticker, (m.get(c.ticker) ?? 0) + 1);
      }
    }
    return m;
  }, [query.data]);

  // Lista única de países disponibles
  const countries = React.useMemo(() => {
    if (!query.data) return [];
    return Array.from(
      new Set(
        query.data.companies.map((c) => c.country).filter((v): v is string => !!v),
      ),
    ).sort();
  }, [query.data]);

  // Filtrado + orden
  const filteredData = React.useMemo(() => {
    if (!query.data) return null;
    const q = search.trim().toLowerCase();

    let companies = query.data.companies.slice();
    if (q) {
      companies = companies.filter(
        (c) =>
          c.ticker.toLowerCase().includes(q) ||
          (c.name && c.name.toLowerCase().includes(q)),
      );
    }
    if (onlySelected) {
      companies = companies.filter((c) => (selectedCounts.get(c.ticker) ?? 0) > 0);
    }
    if (country !== ALL_COUNTRIES) {
      companies = companies.filter((c) => c.country === country);
    }

    // Orden: selected_count DESC, luego ticker ASC
    companies.sort((a, b) => {
      const ca = selectedCounts.get(a.ticker) ?? 0;
      const cb = selectedCounts.get(b.ticker) ?? 0;
      if (cb !== ca) return cb - ca;
      return a.ticker.localeCompare(b.ticker);
    });

    return { ...query.data, companies };
  }, [query.data, search, onlySelected, country, selectedCounts]);

  const status = query.isLoading
    ? "loading"
    : query.error
      ? "error"
      : filteredData && filteredData.weeks.length === 0
        ? "empty"
        : "ready";

  const totalCompanies = query.data?.companies.length ?? 0;
  const shownCompanies = filteredData?.companies.length ?? 0;
  const filtersActive = !!search || onlySelected || country !== ALL_COUNTRIES;

  const resetFilters = () => {
    setSearch("");
    setOnlySelected(false);
    setCountry(ALL_COUNTRIES);
  };

  return (
    <>
      <PageHeader
        title="Mapa histórico de selección"
        description={`Ventana: ${from} → ${to} (${windowWeeks} semanas)`}
        actions={
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setWindowWeeks((w) => Math.max(8, w - 8))}
              disabled={windowWeeks <= 8}
              aria-label="Reducir ventana"
            >
              −8 sem
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setWindowWeeks((w) => Math.min(156, w + 8))}
              disabled={windowWeeks >= 156}
              aria-label="Ampliar ventana"
            >
              +8 sem
            </Button>
          </div>
        }
      />

      <FiltersBar
        search={search}
        onSearch={setSearch}
        onlySelected={onlySelected}
        onOnlySelectedChange={setOnlySelected}
        country={country}
        onCountryChange={setCountry}
        countries={countries}
        filtersActive={filtersActive}
        onReset={resetFilters}
        totalCompanies={totalCompanies}
        shownCompanies={shownCompanies}
      />

      <DataState
        status={status}
        data={filteredData ?? undefined}
        error={query.error ?? undefined}
        onRetry={() => void query.refetch()}
      >
        {(data) => (
          <SelectionMatrix data={data} selectedCounts={selectedCounts} />
        )}
      </DataState>
    </>
  );
}

function FiltersBar({
  search,
  onSearch,
  onlySelected,
  onOnlySelectedChange,
  country,
  onCountryChange,
  countries,
  filtersActive,
  onReset,
  totalCompanies,
  shownCompanies,
}: {
  search: string;
  onSearch: (v: string) => void;
  onlySelected: boolean;
  onOnlySelectedChange: (v: boolean) => void;
  country: string;
  onCountryChange: (v: string) => void;
  countries: string[];
  filtersActive: boolean;
  onReset: () => void;
  totalCompanies: number;
  shownCompanies: number;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-end gap-3 rounded-md border bg-card p-3">
      <div className="relative min-w-[220px] flex-1">
        <Label htmlFor="matrix-search" className="text-xs text-muted-foreground">
          Buscar empresa
        </Label>
        <div className="relative">
          <Search
            className="pointer-events-none absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            id="matrix-search"
            value={search}
            onChange={(e) => onSearch(e.target.value)}
            placeholder="Ticker o nombre…"
            className="pl-8 pr-8"
          />
          {search && (
            <button
              type="button"
              onClick={() => onSearch("")}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              aria-label="Limpiar búsqueda"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      <div className="min-w-[180px]">
        <Label className="text-xs text-muted-foreground">País</Label>
        <Select value={country} onValueChange={onCountryChange}>
          <SelectTrigger>
            <SelectValue placeholder="Todos" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_COUNTRIES}>Todos</SelectItem>
            {countries.map((c) => (
              <SelectItem key={c} value={c}>
                {c}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="flex items-end gap-2 pb-1">
        <Checkbox
          id="only-selected"
          checked={onlySelected}
          onCheckedChange={(v) => onOnlySelectedChange(v === true)}
        />
        <Label htmlFor="only-selected" className="cursor-pointer text-sm">
          Solo seleccionadas
        </Label>
      </div>

      <div className="ml-auto flex items-center gap-3 pb-1">
        <span className="text-xs text-muted-foreground" aria-live="polite">
          {filtersActive
            ? `Mostrando ${shownCompanies} de ${totalCompanies}`
            : `${totalCompanies} empresas`}
        </span>
        {filtersActive && (
          <Button variant="ghost" size="sm" onClick={onReset}>
            Limpiar filtros
          </Button>
        )}
      </div>
    </div>
  );
}
