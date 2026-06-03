"""Puertos definidos por el dominio (F2 §4.8).

Inversión de dependencias: el dominio define las interfaces que necesita; los
adaptadores (infraestructura) las implementan. Pueden mockearse trivialmente
en tests unitarios y de integración.

Todos los métodos son `async` para consistencia con FastAPI/arq.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol, runtime_checkable

from app.domain.backtesting.parameters import BacktestId
from app.domain.screening.read_models import AnalysisRun, Pick
from app.domain.shared.ticker import TickerSymbol


# ───────────────────────────── Tipos compartidos ─────────────────────────────


@dataclass(frozen=True, slots=True)
class PriceRequest:
    """Petición unitaria al `PriceProviderPort.warm_up()`."""

    ticker: TickerSymbol
    day: date


@dataclass(frozen=True, slots=True)
class FxRequest:
    """Petición unitaria de FX al `PriceProviderPort.warm_up_fx()`."""

    pair: str
    day: date


class PriceUnavailableError(Exception):
    """Lanzada por `get_ohlc`/`get_fx` si el dato no está en caché y
    no se solicitó vía `warm_up`/`warm_up_fx`."""


# ───────────────────────────── Puertos ─────────────────────────────


@runtime_checkable
class AnalysisReadPort(Protocol):
    """Lectura del contexto Análisis (BBDD legacy de Railway, F2 §4.4)."""

    async def list_runs_in_period(
        self, *, period_start_iso: str, period_end_iso: str
    ) -> list[AnalysisRun]:
        """Lista los runs cuya `fechaRun` cae en [start, end] (fechas
        inclusivas, formato `YYYY-MM-DD` en zona NY).

        El adaptador (ACL) es responsable de:
        - Traducir el casing sucio externo a `AnalysisRun` limpios.
        - Disparar `analysis_schema_mismatch` si el esquema no coincide
          (F1 §7.3 / F2 §3).
        - Precomputar `pick_count` (COUNT(*) FROM portfolios WHERE id_run=...).
        """
        ...

    async def get_picks_for_run(self, *, run_id: int) -> list[Pick]:
        """Picks del run (filas de `portfolios` con id_run = run_id)."""
        ...


@runtime_checkable
class PriceProviderPort(Protocol):
    """Acceso a precios OHLC y FX, con calentamiento en lote (F2 §4.9)."""

    async def warm_up(self, requests: Iterable[PriceRequest]) -> None:
        """Asegura que todos los OHLC pedidos están en caché tras la llamada.

        El adaptador lee de la caché local y descarga de yfinance lo ausente
        en lote. Si yfinance falla aquí, lanza `PriceUnavailableError`: el
        backtest falla limpio antes de iniciar la rotación (F2 §4.9 paso 3).
        """
        ...

    async def warm_up_fx(self, requests: Iterable[FxRequest]) -> None:
        """Igual que `warm_up` pero para FX."""
        ...

    async def get_ohlc(self, ticker: TickerSymbol, day: date) -> "OHLC":
        """Devuelve OHLC en caché. Lanza `PriceUnavailableError` si no se
        llamó a `warm_up` antes con esta petición."""
        ...

    async def get_fx(self, pair: str, day: date) -> Decimal:
        """Tipo de cambio en caché. Lanza `PriceUnavailableError` si no se
        llamó a `warm_up_fx`."""
        ...

    async def get_currency_for(self, ticker: TickerSymbol) -> str:
        """Divisa de cotización del ticker (`stock.currency` en la legacy).

        No es OHLC pero es esencial para decidir cuándo aplicar FX.
        """
        ...


@runtime_checkable
class BacktestRepositoryPort(Protocol):
    """Persistencia del agregado `Backtest` (F2 §4.8)."""

    async def save(self, backtest: "Backtest") -> None:
        """Guarda el agregado completo (raíz + snapshot + resultado + curva).

        El adaptador es responsable de la transacción: o se guarda todo
        coherente o no se guarda nada.
        """
        ...

    async def get(self, backtest_id: BacktestId) -> "Backtest | None":
        """Recupera el agregado completo o `None` si no existe."""
        ...


@runtime_checkable
class CancellationToken(Protocol):
    """Señal cooperativa de cancelación (F2 §6.5, §9.7, ADR-0005).

    El `BacktestEngine` consulta este token entre semanas. Si el caller
    (worker arq) la marca, el engine aborta limpiamente.

    Async: el adapter real consulta BBDD entre semanas para detectar que el
    endpoint `POST /backtests/{id}/cancel` haya cambiado el estado a
    `cancelled`. Mantenerlo async permite ese acceso a infraestructura sin
    bloquear el event loop.
    """

    async def is_cancelled(self) -> bool:
        ...


# Imports diferidos para evitar ciclos. El dominio se carga por capas:
# parameters → snapshot → result → ports (este módulo) → backtest → engine.
from app.domain.backtesting.snapshot import OHLC  # noqa: E402, F401
