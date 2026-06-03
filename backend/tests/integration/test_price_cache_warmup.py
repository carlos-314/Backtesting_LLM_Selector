"""Tests de integración del `CachedPriceProvider` (F2 §4.9, §8.3).

Postgres real (caché en `price_cache_daily`/`fx_daily` de la BBDD propia)
y yfinance mockeado vía `FakeYfinanceClient` — patrón F2 §8.5.

Lo que F2 §8.3 exige cubrir aquí:
- "el warm-up descarga solo lo ausente y reutiliza lo presente"
- "un fallo de yfinance en el calentamiento deja el backtest `failed` limpio
  antes de calcular" (cubrirá pieza 8 con el engine real; aquí: el provider
  lanza `PriceUnavailableError` y no persiste basura).
"""
from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.backtesting.ports import FxRequest, PriceRequest, PriceUnavailableError
from app.domain.shared.ticker import TickerSymbol
from app.infrastructure.persistence.app_db import SessionFactory
from app.infrastructure.persistence.models.cache import FxDaily, PriceCacheDaily
from app.infrastructure.price_provider.cached_price_provider import CachedPriceProvider
from app.infrastructure.price_provider.yfinance_client import OHLCRow

from tests.integration.fake_yfinance import FakeYfinanceClient


# ────────────────────────── fixtures ──────────────────────────


@pytest.fixture
async def db() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as s:
        yield s


@pytest.fixture(autouse=True)
async def _wipe_cache() -> None:
    async with SessionFactory() as s:
        await s.execute(text("DELETE FROM price_cache_daily"))
        await s.execute(text("DELETE FROM fx_daily"))
        await s.commit()


def _row(o="100", h=None, l=None, c="103", cur="USD") -> OHLCRow:
    """Helper que mantiene OHLC consistente si solo se pasa close."""
    open_d = Decimal(o)
    close_d = Decimal(c)
    high_d = Decimal(h) if h is not None else max(open_d, close_d)
    low_d = Decimal(l) if l is not None else min(open_d, close_d)
    return OHLCRow(
        open=open_d,
        high=high_d,
        low=low_d,
        close=close_d,
        adj_close=close_d,
        volume=1_000_000,
        currency=cur,
    )


# ───────────────────────── warm_up OHLC ─────────────────────────


async def test_warm_up_descarga_y_persiste_lo_ausente(db: AsyncSession) -> None:
    yf = FakeYfinanceClient()
    yf.set_ohlc("AAPL", date(2026, 1, 5), _row())
    provider = CachedPriceProvider(db, yf)

    await provider.warm_up([PriceRequest(TickerSymbol("AAPL"), date(2026, 1, 5))])

    rows = (await db.execute(select(PriceCacheDaily))).scalars().all()
    assert len(rows) == 1
    assert rows[0].ticker == "AAPL"
    assert rows[0].price_date == date(2026, 1, 5)
    assert rows[0].close == Decimal("103")
    assert len(yf.fetch_ohlc_calls) == 1


async def test_warm_up_no_descarga_si_todo_esta_en_cache(db: AsyncSession) -> None:
    """F2 §4.9: descarga solo lo ausente. Si todo está, 0 llamadas a yfinance."""
    yf = FakeYfinanceClient()
    yf.set_ohlc("AAPL", date(2026, 1, 5), _row())
    provider = CachedPriceProvider(db, yf)

    # Primera llamada → descarga
    await provider.warm_up([PriceRequest(TickerSymbol("AAPL"), date(2026, 1, 5))])
    assert len(yf.fetch_ohlc_calls) == 1

    # Segunda llamada con el mismo dato → NO descarga
    await provider.warm_up([PriceRequest(TickerSymbol("AAPL"), date(2026, 1, 5))])
    assert len(yf.fetch_ohlc_calls) == 1


async def test_warm_up_descarga_solo_lo_ausente_no_lo_cacheado(db: AsyncSession) -> None:
    yf = FakeYfinanceClient()
    # Pre-cachear manualmente AAPL@5/Ene
    db.add(
        PriceCacheDaily(
            ticker="AAPL", price_date=date(2026, 1, 5),
            open=Decimal("100"), high=Decimal("105"), low=Decimal("98"), close=Decimal("103"),
            currency="USD",
        )
    )
    await db.commit()

    yf.set_ohlc("AAPL", date(2026, 1, 12), _row(c="104"))
    yf.set_ohlc("MSFT", date(2026, 1, 5), _row(c="200"))

    provider = CachedPriceProvider(db, yf)
    await provider.warm_up([
        PriceRequest(TickerSymbol("AAPL"), date(2026, 1, 5)),   # ya en caché
        PriceRequest(TickerSymbol("AAPL"), date(2026, 1, 12)),  # falta
        PriceRequest(TickerSymbol("MSFT"), date(2026, 1, 5)),   # falta
    ])

    assert len(yf.fetch_ohlc_calls) == 2  # AAPL nuevo rango + MSFT, NO AAPL@5/Ene

    rows = (await db.execute(select(PriceCacheDaily).order_by(PriceCacheDaily.ticker, PriceCacheDaily.price_date))).scalars().all()
    assert len(rows) == 3
    assert [(r.ticker, r.price_date) for r in rows] == [
        ("AAPL", date(2026, 1, 5)),
        ("AAPL", date(2026, 1, 12)),
        ("MSFT", date(2026, 1, 5)),
    ]


async def test_warm_up_lista_vacia_no_hace_nada(db: AsyncSession) -> None:
    yf = FakeYfinanceClient()
    provider = CachedPriceProvider(db, yf)
    await provider.warm_up([])
    assert yf.fetch_ohlc_calls == []


async def test_warm_up_agrupa_por_ticker_un_rango_por_ticker(db: AsyncSession) -> None:
    """Optimización del adapter: una sola llamada yfinance por ticker
    cubriendo todo el rango necesitado para ese ticker."""
    yf = FakeYfinanceClient()
    for d in [date(2026, 1, 5), date(2026, 1, 12), date(2026, 1, 19)]:
        yf.set_ohlc("AAPL", d, _row())
        yf.set_ohlc("MSFT", d, _row())

    provider = CachedPriceProvider(db, yf)
    requests = [
        PriceRequest(TickerSymbol("AAPL"), date(2026, 1, 5)),
        PriceRequest(TickerSymbol("AAPL"), date(2026, 1, 12)),
        PriceRequest(TickerSymbol("AAPL"), date(2026, 1, 19)),
        PriceRequest(TickerSymbol("MSFT"), date(2026, 1, 5)),
        PriceRequest(TickerSymbol("MSFT"), date(2026, 1, 12)),
    ]
    await provider.warm_up(requests)

    # 2 tickers → 2 llamadas batch, NO 5 llamadas individuales.
    assert len(yf.fetch_ohlc_calls) == 2


async def test_warm_up_yfinance_falla_lanza_price_unavailable_no_persiste(
    db: AsyncSession,
) -> None:
    """F2 §4.9 paso 3: si yfinance falla, el backtest debe fallar limpio
    SIN dejar datos parciales en caché."""
    yf = FakeYfinanceClient()
    yf.fail_on_ohlc = RuntimeError("yfinance 503")
    provider = CachedPriceProvider(db, yf)

    with pytest.raises(PriceUnavailableError, match="yfinance failed"):
        await provider.warm_up([PriceRequest(TickerSymbol("AAPL"), date(2026, 1, 5))])

    # No quedó nada en la caché tras el fallo
    rows = (await db.execute(select(PriceCacheDaily))).scalars().all()
    assert rows == []


# ───────────────────────── get_ohlc ─────────────────────────


async def test_get_ohlc_devuelve_dato_si_esta_en_cache(db: AsyncSession) -> None:
    yf = FakeYfinanceClient()
    yf.set_ohlc("AAPL", date(2026, 1, 5), _row(c="150"))
    provider = CachedPriceProvider(db, yf)
    await provider.warm_up([PriceRequest(TickerSymbol("AAPL"), date(2026, 1, 5))])

    ohlc = await provider.get_ohlc(TickerSymbol("AAPL"), date(2026, 1, 5))
    assert ohlc.close == Decimal("150")
    assert ohlc.currency == "USD"


async def test_get_ohlc_sin_warmup_lanza_price_unavailable(db: AsyncSession) -> None:
    yf = FakeYfinanceClient()
    provider = CachedPriceProvider(db, yf)
    with pytest.raises(PriceUnavailableError, match="not in cache"):
        await provider.get_ohlc(TickerSymbol("AAPL"), date(2026, 1, 5))


# ───────────────────────── warm_up FX ─────────────────────────


async def test_warm_up_fx_descarga_y_persiste(db: AsyncSession) -> None:
    yf = FakeYfinanceClient()
    yf.set_fx("CAD/USD", date(2026, 1, 5), Decimal("0.74"))
    provider = CachedPriceProvider(db, yf)

    await provider.warm_up_fx([FxRequest("CAD/USD", date(2026, 1, 5))])

    rows = (await db.execute(select(FxDaily))).scalars().all()
    assert len(rows) == 1
    assert rows[0].pair == "CAD/USD"
    assert rows[0].rate == Decimal("0.74")


async def test_warm_up_fx_no_descarga_si_todo_en_cache(db: AsyncSession) -> None:
    yf = FakeYfinanceClient()
    yf.set_fx("CAD/USD", date(2026, 1, 5), Decimal("0.74"))
    provider = CachedPriceProvider(db, yf)
    await provider.warm_up_fx([FxRequest("CAD/USD", date(2026, 1, 5))])
    await provider.warm_up_fx([FxRequest("CAD/USD", date(2026, 1, 5))])
    assert len(yf.fetch_fx_calls) == 1


async def test_warm_up_fx_falla_no_persiste(db: AsyncSession) -> None:
    yf = FakeYfinanceClient()
    yf.fail_on_fx = RuntimeError("fx server down")
    provider = CachedPriceProvider(db, yf)
    with pytest.raises(PriceUnavailableError, match="yfinance FX"):
        await provider.warm_up_fx([FxRequest("CAD/USD", date(2026, 1, 5))])

    rows = (await db.execute(select(FxDaily))).scalars().all()
    assert rows == []


# ───────────────────────── get_fx ─────────────────────────


async def test_get_fx_devuelve_rate_si_esta_en_cache(db: AsyncSession) -> None:
    yf = FakeYfinanceClient()
    yf.set_fx("CAD/USD", date(2026, 1, 5), Decimal("0.74"))
    provider = CachedPriceProvider(db, yf)
    await provider.warm_up_fx([FxRequest("CAD/USD", date(2026, 1, 5))])
    assert await provider.get_fx("CAD/USD", date(2026, 1, 5)) == Decimal("0.74")


async def test_get_fx_sin_warmup_lanza_error(db: AsyncSession) -> None:
    yf = FakeYfinanceClient()
    provider = CachedPriceProvider(db, yf)
    with pytest.raises(PriceUnavailableError, match="not in cache"):
        await provider.get_fx("CAD/USD", date(2026, 1, 5))


# ───────────────────────── get_currency_for ─────────────────────────


async def test_get_currency_for_lee_de_cache_si_existe(db: AsyncSession) -> None:
    """Optimización: si ya descargamos OHLC del ticker, su currency está en caché."""
    yf = FakeYfinanceClient()
    yf.set_ohlc("TSE", date(2026, 1, 5), _row(cur="CAD"))
    provider = CachedPriceProvider(db, yf)
    await provider.warm_up([PriceRequest(TickerSymbol("TSE"), date(2026, 1, 5))])

    cur = await provider.get_currency_for(TickerSymbol("TSE"))
    assert cur == "CAD"
    # No llama a fetch_currency: la sacó de la caché de OHLC
    assert yf.fetch_currency_calls == []


async def test_get_currency_for_pregunta_a_yfinance_si_no_hay_cache(
    db: AsyncSession,
) -> None:
    yf = FakeYfinanceClient()
    yf.set_currency("AAPL", "USD")
    provider = CachedPriceProvider(db, yf)
    cur = await provider.get_currency_for(TickerSymbol("AAPL"))
    assert cur == "USD"
    assert yf.fetch_currency_calls == ["AAPL"]


async def test_get_currency_for_yfinance_falla_lanza_price_unavailable(
    db: AsyncSession,
) -> None:
    yf = FakeYfinanceClient()
    yf.fail_on_currency = RuntimeError("offline")
    provider = CachedPriceProvider(db, yf)
    with pytest.raises(PriceUnavailableError, match="Cannot determine currency"):
        await provider.get_currency_for(TickerSymbol("AAPL"))
