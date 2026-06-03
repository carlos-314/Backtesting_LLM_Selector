"""Cliente yfinance encapsulado tras un Protocol (F1 §8.1 frontera mockeable).

Es el único sitio del backend que conoce yfinance. Si yfinance cambia su
API o lo sustituimos, el impacto queda contenido aquí.

El Protocol permite:
- Una implementación real (`YfinanceClientImpl`) en runtime.
- Fakes en tests (F2 §8.5: "yfinance siempre mockeado").
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class OHLCRow:
    """Fila OHLC + adj_close + volume + currency descargada de yfinance."""

    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal | None
    adj_close: Decimal | None
    volume: int | None
    currency: str


@runtime_checkable
class YfinanceClient(Protocol):
    """Contrato del cliente de mercado. Los métodos son async aunque yfinance
    es síncrono — la implementación real envuelve con `asyncio.to_thread`."""

    async def fetch_ohlc(
        self, tickers: list[str], start: date, end_exclusive: date
    ) -> dict[tuple[str, date], OHLCRow]:
        """Descarga OHLC para varios tickers y un rango [start, end_exclusive).

        Devuelve un dict `(ticker, day) → OHLCRow`. Si yfinance no devuelve
        dato para algún (ticker, día) — p.ej. mercado cerrado —, esa entrada
        simplemente no aparece en el dict.

        Lanza si yfinance falla (red caída, API broken, etc.). El llamador
        traduce eso a `PriceUnavailableError` del dominio.
        """
        ...

    async def fetch_fx(
        self, pair: str, start: date, end_exclusive: date
    ) -> dict[date, Decimal]:
        """Descarga FX (close diario) para un par en un rango.

        `pair` con formato `BASE/QUOTE` (ej. `CAD/USD`).
        """
        ...

    async def fetch_currency(self, ticker: str) -> str:
        """Divisa de cotización del ticker (info.currency en yfinance)."""
        ...
