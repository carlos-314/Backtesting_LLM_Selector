"""Implementación de `PriceProviderPort` con caché Postgres + yfinance (F2 §4.9).

Flujo de `warm_up`:
1. Consultar `price_cache_daily` por las claves `(ticker, day)` pedidas.
2. Para los faltantes, agruparlos por ticker; para cada ticker descargar
   yfinance UN solo rango cubriendo todas sus fechas. Reduce drásticamente
   el número de descargas (lo ausente, en lote — F2 §4.9 paso 3).
3. Persistir todo lo descargado en `price_cache_daily`.
4. Si yfinance falla en cualquier punto → `PriceUnavailableError`, sin
   persistir nada parcial (decisión: rollback de la transacción).

`get_ohlc` y `get_fx` SOLO leen caché; si el dato no se calentó antes,
lanzan `PriceUnavailableError`. Esto fuerza el patrón "warm-up explícito
arriba" que F2 §4.9 prescribe.
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.backtesting.ports import (
    FxRequest,
    PriceRequest,
    PriceUnavailableError,
)
from app.domain.backtesting.snapshot import OHLC
from app.domain.shared.ticker import TickerSymbol
from app.infrastructure.persistence.models.cache import FxDaily, PriceCacheDaily
from app.infrastructure.price_provider.yfinance_client import (
    OHLCRow,
    YfinanceClient,
)


class CachedPriceProvider:
    """Implementación de `PriceProviderPort` (F2 §4.8) con caché en Postgres."""

    def __init__(self, session: AsyncSession, client: YfinanceClient) -> None:
        self._session = session
        self._client = client

    # ─────────────────────────── warm-up OHLC ───────────────────────────

    async def warm_up(self, requests: Iterable[PriceRequest]) -> None:
        req_set = {(r.ticker, r.day) for r in requests}
        if not req_set:
            return

        # 1) ¿Qué ya está en caché?
        cached_keys = await self._cached_ohlc_keys(req_set)
        missing = req_set - cached_keys
        if not missing:
            return

        # 2) Agrupar por ticker → un solo rango por ticker
        by_ticker: dict[TickerSymbol, list[date]] = {}
        for tk, day in missing:
            by_ticker.setdefault(tk, []).append(day)

        try:
            for tk, days in by_ticker.items():
                start, end_excl = min(days), max(days) + timedelta(days=1)
                rows = await self._client.fetch_ohlc(
                    [str(tk)], start=start, end_exclusive=end_excl
                )
                await self._persist_ohlc(tk, rows)
        except PriceUnavailableError:
            await self._session.rollback()
            raise
        except Exception as exc:  # noqa: BLE001 — frontera externa
            await self._session.rollback()
            raise PriceUnavailableError(f"yfinance failed: {exc}") from exc

        await self._session.commit()

    # ─────────────────────────── warm-up FX ───────────────────────────

    async def warm_up_fx(self, requests: Iterable[FxRequest]) -> None:
        req_set = {(r.pair, r.day) for r in requests}
        if not req_set:
            return

        cached_keys = await self._cached_fx_keys(req_set)
        missing = req_set - cached_keys
        if not missing:
            return

        by_pair: dict[str, list[date]] = {}
        for pair, day in missing:
            by_pair.setdefault(pair, []).append(day)

        try:
            for pair, days in by_pair.items():
                start, end_excl = min(days), max(days) + timedelta(days=1)
                rows = await self._client.fetch_fx(pair, start=start, end_exclusive=end_excl)
                await self._persist_fx(pair, rows)
        except PriceUnavailableError:
            await self._session.rollback()
            raise
        except Exception as exc:  # noqa: BLE001
            await self._session.rollback()
            raise PriceUnavailableError(f"yfinance FX failed: {exc}") from exc

        await self._session.commit()

    # ─────────────────────────── lecturas caché ───────────────────────────

    async def get_ohlc(self, ticker: TickerSymbol, day: date) -> OHLC:
        stmt = select(PriceCacheDaily).where(
            PriceCacheDaily.ticker == str(ticker),
            PriceCacheDaily.price_date == day,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None or row.open is None or row.close is None:
            raise PriceUnavailableError(
                f"OHLC not in cache for {ticker} on {day}; warm_up before get_ohlc"
            )
        # OHLC del dominio exige low<=open/close<=high. yfinance lo garantiza,
        # pero defensa por si llega ruido: si la invariante no se cumple,
        # tratamos como dato corrupto y devolvemos PriceUnavailableError.
        try:
            return OHLC(
                open=row.open,
                high=row.high or row.open,
                low=row.low or row.open,
                close=row.close,
                currency=row.currency,
            )
        except ValueError as exc:
            raise PriceUnavailableError(
                f"OHLC for {ticker} on {day} fails domain invariants: {exc}"
            ) from exc

    async def get_fx(self, pair: str, day: date) -> Decimal:
        stmt = select(FxDaily).where(FxDaily.pair == pair, FxDaily.date == day)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise PriceUnavailableError(
                f"FX not in cache for {pair} on {day}; warm_up_fx before get_fx"
            )
        return row.rate

    async def get_currency_for(self, ticker: TickerSymbol) -> str:
        """Lee la divisa de la caché si la hay; si no, pregunta a yfinance."""
        stmt = select(PriceCacheDaily.currency).where(PriceCacheDaily.ticker == str(ticker)).limit(1)
        cached = (await self._session.execute(stmt)).scalar_one_or_none()
        if cached:
            return cached
        try:
            return await self._client.fetch_currency(str(ticker))
        except Exception as exc:  # noqa: BLE001
            raise PriceUnavailableError(
                f"Cannot determine currency for {ticker}: {exc}"
            ) from exc

    # ─────────────────────────── helpers de caché ───────────────────────────

    async def _cached_ohlc_keys(
        self, req_set: set[tuple[TickerSymbol, date]]
    ) -> set[tuple[TickerSymbol, date]]:
        if not req_set:
            return set()
        ticker_strs = list({str(tk) for tk, _ in req_set})
        days = list({d for _, d in req_set})
        stmt = select(PriceCacheDaily.ticker, PriceCacheDaily.price_date).where(
            PriceCacheDaily.ticker.in_(ticker_strs),
            PriceCacheDaily.price_date.in_(days),
        )
        result = await self._session.execute(stmt)
        return {(TickerSymbol(t), d) for t, d in result.all()}

    async def _cached_fx_keys(
        self, req_set: set[tuple[str, date]]
    ) -> set[tuple[str, date]]:
        if not req_set:
            return set()
        pairs = list({p for p, _ in req_set})
        days = list({d for _, d in req_set})
        stmt = select(FxDaily.pair, FxDaily.date).where(
            FxDaily.pair.in_(pairs),
            FxDaily.date.in_(days),
        )
        result = await self._session.execute(stmt)
        return {(p, d) for p, d in result.all()}

    async def _persist_ohlc(
        self, ticker: TickerSymbol, rows: dict[tuple[str, date], OHLCRow]
    ) -> None:
        if not rows:
            return
        # `INSERT ... ON CONFLICT DO NOTHING` para idempotencia: si entre el
        # `_cached_ohlc_keys` y este insert otro proceso pobló la caché, no
        # duplicamos ni petamos.
        values = [
            {
                "ticker": str(ticker),
                "price_date": day,
                "open": row.open,
                "high": row.high,
                "low": row.low,
                "close": row.close,
                "adj_close": row.adj_close,
                "volume": row.volume,
                "currency": row.currency,
                "source": "yfinance",
            }
            for (_t, day), row in rows.items()
        ]
        stmt = insert(PriceCacheDaily).values(values)
        stmt = stmt.on_conflict_do_nothing(index_elements=["ticker", "price_date"])
        await self._session.execute(stmt)

    async def _persist_fx(self, pair: str, rows: dict[date, Decimal]) -> None:
        if not rows:
            return
        values = [
            {"pair": pair, "date": day, "rate": rate, "source": "yfinance"}
            for day, rate in rows.items()
        ]
        stmt = insert(FxDaily).values(values)
        stmt = stmt.on_conflict_do_nothing(index_elements=["pair", "date"])
        await self._session.execute(stmt)
