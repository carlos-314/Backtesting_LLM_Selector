"""Implementación real de `YfinanceClient` (F1 §8.1 frontera frágil).

yfinance es síncrono → envolvemos cada llamada con `asyncio.to_thread`
para no bloquear el event loop del worker.

**No hay tests automáticos** para esta implementación: F2 §8.5 dice
"yfinance siempre mockeado", confirmado por F1 §8.1. La validación es
manual (test de humo cuando se arranca contra yfinance real).

Si yfinance cambiase su API, este es el ÚNICO archivo a modificar.
"""
from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal, InvalidOperation

import yfinance as yf  # type: ignore[import-untyped]

from app.infrastructure.price_provider.yfinance_client import OHLCRow


def _to_decimal(v: object) -> Decimal | None:
    """Convierte un escalar pandas/float a Decimal de forma segura."""
    if v is None:
        return None
    try:
        # Decimal(float) es preciso pero ruidoso; pasar por str evita
        # arrastrar la imprecisión binaria de un float "150.0000000001".
        return Decimal(str(v))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _to_int(v: object) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


class YfinanceClientImpl:
    """Wrapper async sobre yfinance."""

    async def fetch_ohlc(
        self, tickers: list[str], start: date, end_exclusive: date
    ) -> dict[tuple[str, date], OHLCRow]:
        return await asyncio.to_thread(self._fetch_ohlc_sync, tickers, start, end_exclusive)

    async def fetch_fx(
        self, pair: str, start: date, end_exclusive: date
    ) -> dict[date, Decimal]:
        return await asyncio.to_thread(self._fetch_fx_sync, pair, start, end_exclusive)

    async def fetch_currency(self, ticker: str) -> str:
        return await asyncio.to_thread(self._fetch_currency_sync, ticker)

    # ──────────────────────── implementaciones sync ────────────────────────

    def _fetch_ohlc_sync(
        self, tickers: list[str], start: date, end_exclusive: date
    ) -> dict[tuple[str, date], OHLCRow]:
        df = yf.download(
            tickers=" ".join(tickers),
            start=start.isoformat(),
            end=end_exclusive.isoformat(),
            group_by="ticker",
            auto_adjust=False,
            progress=False,
        )
        out: dict[tuple[str, date], OHLCRow] = {}
        if df is None or df.empty:
            return out

        # Cuando hay 1 ticker yfinance NO agrupa por ticker (df tiene
        # columnas Open/High/Low/Close/Adj Close/Volume directamente).
        # Cuando hay N tickers el primer nivel del MultiIndex es el ticker.
        if len(tickers) == 1:
            single = tickers[0]
            for idx, row in df.iterrows():
                day = idx.date() if hasattr(idx, "date") else idx
                currency = "USD"  # `info` requiere otra llamada; lo dejamos
                out[(single, day)] = OHLCRow(
                    open=_to_decimal(row.get("Open")),
                    high=_to_decimal(row.get("High")),
                    low=_to_decimal(row.get("Low")),
                    close=_to_decimal(row.get("Close")),
                    adj_close=_to_decimal(row.get("Adj Close")),
                    volume=_to_int(row.get("Volume")),
                    currency=currency,
                )
        else:
            for tk in tickers:
                if tk not in df.columns.get_level_values(0):
                    continue
                sub = df[tk]
                for idx, row in sub.iterrows():
                    day = idx.date() if hasattr(idx, "date") else idx
                    out[(tk, day)] = OHLCRow(
                        open=_to_decimal(row.get("Open")),
                        high=_to_decimal(row.get("High")),
                        low=_to_decimal(row.get("Low")),
                        close=_to_decimal(row.get("Close")),
                        adj_close=_to_decimal(row.get("Adj Close")),
                        volume=_to_int(row.get("Volume")),
                        currency="USD",
                    )
        return out

    def _fetch_fx_sync(
        self, pair: str, start: date, end_exclusive: date
    ) -> dict[date, Decimal]:
        # yfinance representa FX como tickers con sufijo `=X`.
        # "CAD/USD" → "CADUSD=X". Mantenemos `pair` con barra en nuestro contrato.
        base, quote = pair.split("/")
        symbol = f"{base}{quote}=X"
        df = yf.download(
            tickers=symbol,
            start=start.isoformat(),
            end=end_exclusive.isoformat(),
            auto_adjust=False,
            progress=False,
        )
        out: dict[date, Decimal] = {}
        if df is None or df.empty:
            return out
        for idx, row in df.iterrows():
            day = idx.date() if hasattr(idx, "date") else idx
            close = _to_decimal(row.get("Close"))
            if close is not None:
                out[day] = close
        return out

    def _fetch_currency_sync(self, ticker: str) -> str:
        try:
            info = yf.Ticker(ticker).fast_info
            return (info.get("currency") or "USD").upper()
        except Exception:
            # `fast_info` puede no estar disponible — fallback al pleno `info`.
            info = yf.Ticker(ticker).info
            return (info.get("currency") or "USD").upper()
