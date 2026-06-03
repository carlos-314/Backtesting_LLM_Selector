"""Fake del `YfinanceClient` para tests de integración (F2 §8.5).

yfinance es la frontera externa frágil que F1 §8.1 ordena mockear siempre.
Este fake permite:
- Pre-cargar OHLC y FX deterministas.
- Contar llamadas (verificar que `warm_up` solo descarga lo ausente).
- Simular fallos.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.infrastructure.price_provider.yfinance_client import OHLCRow


@dataclass
class FakeYfinanceClient:
    ohlc_data: dict[tuple[str, date], OHLCRow] = field(default_factory=dict)
    fx_data: dict[tuple[str, date], Decimal] = field(default_factory=dict)
    currency_for: dict[str, str] = field(default_factory=dict)

    # Observabilidad para tests
    fetch_ohlc_calls: list[tuple[list[str], date, date]] = field(default_factory=list)
    fetch_fx_calls: list[tuple[str, date, date]] = field(default_factory=list)
    fetch_currency_calls: list[str] = field(default_factory=list)

    # Inyección de errores
    fail_on_ohlc: Exception | None = None
    fail_on_fx: Exception | None = None
    fail_on_currency: Exception | None = None

    def set_ohlc(self, ticker: str, day: date, row: OHLCRow) -> None:
        self.ohlc_data[(ticker, day)] = row

    def set_fx(self, pair: str, day: date, rate: Decimal) -> None:
        self.fx_data[(pair, day)] = rate

    def set_currency(self, ticker: str, currency: str) -> None:
        self.currency_for[ticker] = currency

    # ───────────── implementación del Protocol ─────────────

    async def fetch_ohlc(
        self, tickers: list[str], start: date, end_exclusive: date
    ) -> dict[tuple[str, date], OHLCRow]:
        self.fetch_ohlc_calls.append((list(tickers), start, end_exclusive))
        if self.fail_on_ohlc is not None:
            raise self.fail_on_ohlc
        # Devuelve lo pre-cargado dentro del rango pedido y de los tickers
        return {
            (t, d): row
            for (t, d), row in self.ohlc_data.items()
            if t in tickers and start <= d < end_exclusive
        }

    async def fetch_fx(
        self, pair: str, start: date, end_exclusive: date
    ) -> dict[date, Decimal]:
        self.fetch_fx_calls.append((pair, start, end_exclusive))
        if self.fail_on_fx is not None:
            raise self.fail_on_fx
        return {
            d: rate
            for (p, d), rate in self.fx_data.items()
            if p == pair and start <= d < end_exclusive
        }

    async def fetch_currency(self, ticker: str) -> str:
        self.fetch_currency_calls.append(ticker)
        if self.fail_on_currency is not None:
            raise self.fail_on_currency
        if ticker not in self.currency_for:
            raise KeyError(f"FakeYfinanceClient has no currency for {ticker}")
        return self.currency_for[ticker]
