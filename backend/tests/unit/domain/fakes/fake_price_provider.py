"""Fake en memoria del `PriceProviderPort` (F2 §8.5, §8.7).

Pre-cargado con OHLC y FX para fechas concretas. `warm_up` cuenta las
peticiones (útil para verificar que el engine pide en lote y solo lo que
necesita).
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.domain.backtesting.ports import (
    FxRequest,
    PriceRequest,
    PriceUnavailableError,
)
from app.domain.backtesting.snapshot import OHLC
from app.domain.shared.ticker import TickerSymbol


@dataclass
class FakePriceProvider:
    """In-memory implementación del puerto, parametrizable por test.

    Uso:
        provider = FakePriceProvider()
        provider.set_ohlc(TickerSymbol("AAPL"), date(2026, 1, 5),
                          OHLC(Decimal("100"), Decimal("105"), Decimal("98"),
                               Decimal("103"), "USD"))
        provider.set_currency(TickerSymbol("AAPL"), "USD")
    """

    ohlc_data: dict[tuple[TickerSymbol, date], OHLC] = field(default_factory=dict)
    fx_data: dict[tuple[str, date], Decimal] = field(default_factory=dict)
    currency_for: dict[TickerSymbol, str] = field(default_factory=dict)

    # Hooks para tests: contar warm-ups y simular fallos de yfinance.
    warm_up_calls: list[frozenset[PriceRequest]] = field(default_factory=list)
    warm_up_fx_calls: list[frozenset[FxRequest]] = field(default_factory=list)
    fail_on_warm_up: Exception | None = None

    # ─────────────────── Configuración para los tests ───────────────────

    def set_ohlc(self, ticker: TickerSymbol, day: date, ohlc: OHLC) -> None:
        self.ohlc_data[(ticker, day)] = ohlc

    def set_fx(self, pair: str, day: date, rate: Decimal) -> None:
        self.fx_data[(pair, day)] = rate

    def set_currency(self, ticker: TickerSymbol, currency: str) -> None:
        self.currency_for[ticker] = currency

    # ─────────────────── Implementación del puerto ───────────────────

    async def warm_up(self, requests: Iterable[PriceRequest]) -> None:
        req_set = frozenset(requests)
        self.warm_up_calls.append(req_set)
        if self.fail_on_warm_up is not None:
            raise self.fail_on_warm_up
        # En el fake los datos ya están pre-cargados; si falta, es bug del test.
        for req in req_set:
            if (req.ticker, req.day) not in self.ohlc_data:
                raise PriceUnavailableError(
                    f"FakePriceProvider has no OHLC for {req.ticker} on {req.day}; "
                    f"preload it with set_ohlc()"
                )

    async def warm_up_fx(self, requests: Iterable[FxRequest]) -> None:
        req_set = frozenset(requests)
        self.warm_up_fx_calls.append(req_set)
        if self.fail_on_warm_up is not None:
            raise self.fail_on_warm_up
        for req in req_set:
            if (req.pair, req.day) not in self.fx_data:
                raise PriceUnavailableError(
                    f"FakePriceProvider has no FX for {req.pair} on {req.day}"
                )

    async def get_ohlc(self, ticker: TickerSymbol, day: date) -> OHLC:
        try:
            return self.ohlc_data[(ticker, day)]
        except KeyError as e:
            raise PriceUnavailableError(
                f"OHLC not warmed up: {ticker} {day}"
            ) from e

    async def get_fx(self, pair: str, day: date) -> Decimal:
        try:
            return self.fx_data[(pair, day)]
        except KeyError as e:
            raise PriceUnavailableError(f"FX not warmed up: {pair} {day}") from e

    async def get_currency_for(self, ticker: TickerSymbol) -> str:
        return self.currency_for.get(ticker, "USD")
