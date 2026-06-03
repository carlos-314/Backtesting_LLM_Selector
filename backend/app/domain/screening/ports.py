"""Puertos del contexto Screening (F2 §4.4, §4.8).

Misma capa anticorrupción que el `AnalysisReadPort` que usa el backtesting,
pero con métodos adicionales para los endpoints HTTP del visor:

- Detalle de empresa (`get_company_data`).
- Universo de un run (`list_universe_for_run`) — todas las empresas
  analizadas, no sólo las seleccionadas; necesario para la matriz (ADR-0001).
- Metadata catálogo (`get_companies_metadata`) desde `stock`.

Se mantiene como Protocol; la implementación concreta es
`AnalysisAclReader` (la misma clase que implementa el puerto del backtesting).
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from app.domain.screening.read_models import AnalysisRun, Pick
from app.domain.shared.ticker import TickerSymbol


@runtime_checkable
class ScreeningReadPort(Protocol):
    """Lectura del contexto Análisis para los endpoints del visor."""

    async def list_runs_in_period(
        self, *, period_start_iso: str, period_end_iso: str
    ) -> list[AnalysisRun]:
        ...

    async def get_picks_for_run(self, *, run_id: int) -> list[Pick]:
        ...

    async def get_company_data(
        self, *, run_id: int, ticker: TickerSymbol
    ) -> dict[str, Any] | None:
        """Detalle de una empresa de un run. Devuelve un dict con los
        campos canónicos (mapeados desde el casing sucio externo) o `None`
        si no existe.

        El catálogo definitivo está pendiente de ADR-0002 (R2-bis); día
        uno devolvemos un subconjunto mínimo + bloques JSONB.
        """
        ...

    async def list_universe_for_run(self, *, run_id: int) -> list[TickerSymbol]:
        """Tickers de `processed_stocks` para ese run (universo analizado).
        Para la matriz histórica (ADR-0001)."""
        ...

    async def get_companies_metadata(
        self, *, tickers: list[TickerSymbol]
    ) -> dict[TickerSymbol, dict[str, Any]]:
        """Metadata catálogo (nombre, país, divisa) desde `stock` para una
        lista de tickers. Útil para componer la matriz."""
        ...
