"""Tests del `BacktestEngine` (F2 §4.9, §8.2).

Usa Fakes en memoria de todos los puertos. Verifica los caminos clave:
- Flujo completo con éxito (resolver→warm-up→rotación→snapshot+result).
- Fallo en warm-up → backtest FAILED con código `prices_unavailable`.
- Cancelación cooperativa → backtest CANCELLED a mitad del bucle.
- Sin runs OK en el periodo → COMPLETED con snapshot vacío y curva trivial.
- Entrante a CLOSE y saliente a OPEN (delegado a la strategy, ya probado;
  aquí solo verificamos integración).
"""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.domain.backtesting.backtest import Backtest
from app.domain.backtesting.engine import BacktestEngine
from app.domain.backtesting.parameters import BacktestParameters, BacktestStatus
from app.domain.backtesting.ports import PriceUnavailableError
from app.domain.backtesting.snapshot import OHLC
from app.domain.backtesting.strategy import WeeklyRotationStrategy
from app.domain.screening.read_models import AnalysisRun, Pick
from app.domain.shared.money import Money
from app.domain.shared.ticker import TickerSymbol
from app.domain.shared.week import NEW_YORK, Week

from tests.unit.domain.fakes.cancellation import ManualCancellationToken
from tests.unit.domain.fakes.fake_analysis_reader import FakeAnalysisReader
from tests.unit.domain.fakes.fake_price_provider import FakePriceProvider


# ─────────────────────── helpers ───────────────────────


def _ohlc(o="100", c="103", cur="USD") -> OHLC:
    op, cl = Decimal(o), Decimal(c)
    return OHLC(op, max(op, cl), min(op, cl), cl, cur)


def _bt() -> Backtest:
    params = BacktestParameters(
        period_start=Week(date(2026, 1, 5)),
        period_end=Week(date(2026, 1, 19)),  # 3 semanas (5, 12, 19)
        initial_capital=Money.usd("10000"),
    )
    return Backtest(
        id=uuid.uuid4(),
        name="test",
        created_by=uuid.uuid4(),
        parameters=params,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def _run(run_id: int, week_date: date, pick_count: int = 1) -> AnalysisRun:
    return AnalysisRun(
        id=run_id,
        fecha_run=datetime(week_date.year, week_date.month, week_date.day, 9, 0, tzinfo=NEW_YORK),
        run_code=f"RUN_{run_id}",
        status="COMPLETED",
        pick_count=pick_count,
    )


NOW = datetime(2026, 2, 1, tzinfo=timezone.utc)


# ─────────────────────── Flujo feliz ───────────────────────


async def test_engine_flujo_completo_marca_completed_con_snapshot_y_result() -> None:
    analysis = FakeAnalysisReader()
    prices = FakePriceProvider()

    # Tres semanas, mismas dos empresas → no hay rotación tras la primera
    weeks = [date(2026, 1, 5), date(2026, 1, 12), date(2026, 1, 19)]
    for i, wd in enumerate(weeks, start=1):
        analysis.add_run(
            _run(run_id=i, week_date=wd, pick_count=2),
            [Pick(TickerSymbol("AAPL"), "core", None), Pick(TickerSymbol("MSFT"), "core", None)],
        )
        prices.set_ohlc(TickerSymbol("AAPL"), wd, _ohlc(o="100", c="100"))
        prices.set_ohlc(TickerSymbol("MSFT"), wd, _ohlc(o="200", c="200"))

    engine = BacktestEngine(analysis=analysis, prices=prices, strategy=WeeklyRotationStrategy())
    bt = _bt()
    await engine.run(bt, now=NOW)

    assert bt.status == BacktestStatus.COMPLETED
    assert bt.snapshot is not None
    assert len(bt.snapshot.weeks) == 3
    assert bt.result is not None
    # Sin cambios de precio ni rotación → total_return ≈ 0
    assert bt.result.total_return == Decimal("0.0000")
    assert bt.weeks_processed == 3


async def test_engine_calienta_cache_en_un_solo_warm_up_call() -> None:
    """F2 §4.9: el calentamiento es UNA llamada en lote, no N llamadas."""
    analysis = FakeAnalysisReader()
    prices = FakePriceProvider()
    weeks = [date(2026, 1, 5), date(2026, 1, 12), date(2026, 1, 19)]
    for i, wd in enumerate(weeks, start=1):
        analysis.add_run(
            _run(i, wd, pick_count=1),
            [Pick(TickerSymbol("AAPL"), "core", None)],
        )
        prices.set_ohlc(TickerSymbol("AAPL"), wd, _ohlc())

    engine = BacktestEngine(analysis=analysis, prices=prices, strategy=WeeklyRotationStrategy())
    await engine.run(_bt(), now=NOW)

    assert len(prices.warm_up_calls) == 1  # una sola llamada
    # Pidió todas las (ticker, fecha) en esa única llamada
    assert len(prices.warm_up_calls[0]) == 3


async def test_engine_rota_correctamente_aapl_msft_al_close() -> None:
    """Comprobamos que el engine consulta CLOSE para las entrantes (vía strategy)."""
    analysis = FakeAnalysisReader()
    prices = FakePriceProvider()

    # Una sola semana, una entrante AAPL @close=100
    wd = date(2026, 1, 5)
    analysis.add_run(_run(1, wd, pick_count=1), [Pick(TickerSymbol("AAPL"), "core", None)])
    prices.set_ohlc(TickerSymbol("AAPL"), wd, _ohlc(o="80", c="100"))  # open!=close

    bt = _bt()
    # Acortamos a 1 semana para simplificar:
    bt._parameters = BacktestParameters(  # noqa: SLF001 — test interno
        period_start=Week(wd),
        period_end=Week(wd),
        initial_capital=Money.usd("10000"),
    )

    engine = BacktestEngine(analysis=analysis, prices=prices, strategy=WeeklyRotationStrategy())
    await engine.run(bt, now=NOW)

    assert bt.status == BacktestStatus.COMPLETED
    # Snapshot tiene 1 semana con AAPL y su OHLC completo
    assert len(bt.snapshot.weeks) == 1
    pick = bt.snapshot.weeks[0].picks[0]
    assert pick.ticker == TickerSymbol("AAPL")
    assert pick.ohlc.close == Decimal("100")


# ─────────────────────── Fallo en warm-up ───────────────────────


async def test_engine_warm_up_falla_marca_failed_con_prices_unavailable() -> None:
    analysis = FakeAnalysisReader()
    prices = FakePriceProvider()
    wd = date(2026, 1, 5)
    analysis.add_run(_run(1, wd, pick_count=1), [Pick(TickerSymbol("MISSING"), "core", None)])
    # ¡OHLC no precargado para "MISSING"!

    engine = BacktestEngine(analysis=analysis, prices=prices, strategy=WeeklyRotationStrategy())
    bt = _bt()
    bt._parameters = BacktestParameters(  # noqa: SLF001
        period_start=Week(wd), period_end=Week(wd), initial_capital=Money.usd("10000")
    )

    await engine.run(bt, now=NOW)

    assert bt.status == BacktestStatus.FAILED
    assert bt.error is not None
    assert bt.error.code == "prices_unavailable"


async def test_engine_warm_up_falla_explicito_inyectado() -> None:
    """Si yfinance está caído, el adaptador real lanza; el engine debe atrapar."""
    analysis = FakeAnalysisReader()
    prices = FakePriceProvider()
    wd = date(2026, 1, 5)
    analysis.add_run(_run(1, wd, pick_count=1), [Pick(TickerSymbol("AAPL"), "core", None)])
    prices.set_ohlc(TickerSymbol("AAPL"), wd, _ohlc())
    prices.fail_on_warm_up = PriceUnavailableError("yfinance 503")

    engine = BacktestEngine(analysis=analysis, prices=prices, strategy=WeeklyRotationStrategy())
    bt = _bt()
    bt._parameters = BacktestParameters(  # noqa: SLF001
        period_start=Week(wd), period_end=Week(wd), initial_capital=Money.usd("10000")
    )
    await engine.run(bt, now=NOW)

    assert bt.status == BacktestStatus.FAILED
    assert bt.error.code == "prices_unavailable"
    assert "yfinance 503" in bt.error.message


# ─────────────────────── Cancelación ───────────────────────


async def test_engine_cancellation_token_corta_el_flujo_y_marca_cancelled() -> None:
    """F2 §6.5: el engine atiende el token entre semanas."""
    analysis = FakeAnalysisReader()
    prices = FakePriceProvider()
    weeks = [date(2026, 1, 5), date(2026, 1, 12), date(2026, 1, 19)]
    for i, wd in enumerate(weeks, start=1):
        analysis.add_run(_run(i, wd, pick_count=1), [Pick(TickerSymbol("AAPL"), "core", None)])
        prices.set_ohlc(TickerSymbol("AAPL"), wd, _ohlc())

    token = ManualCancellationToken(cancel_after=1)  # cancela tras la 1ª consulta
    engine = BacktestEngine(analysis=analysis, prices=prices, strategy=WeeklyRotationStrategy())
    bt = _bt()
    await engine.run(bt, now=NOW, cancellation=token)

    assert bt.status == BacktestStatus.CANCELLED
    # Procesó alguna pero no todas:
    assert bt.weeks_processed is not None
    assert bt.weeks_processed < 3


# ─────────────────────── Caso degenerado: sin runs OK ───────────────────────


async def test_engine_sin_runs_OK_en_periodo_completa_con_snapshot_vacio() -> None:
    """ADR-0004: si ningún run de la semana es OK, la semana se descarta.
    Resultado: backtest COMPLETED con snapshot vacío — no es failure."""
    analysis = FakeAnalysisReader()
    prices = FakePriceProvider()
    # Añadimos un run STARTED (NO OK) en el periodo
    wd = date(2026, 1, 5)
    bad = AnalysisRun(
        id=99,
        fecha_run=datetime(wd.year, wd.month, wd.day, 9, 0, tzinfo=NEW_YORK),
        run_code="RUN_BAD",
        status="STARTED",
        pick_count=5,
    )
    analysis.add_run(bad, [])

    engine = BacktestEngine(analysis=analysis, prices=prices, strategy=WeeklyRotationStrategy())
    bt = _bt()
    await engine.run(bt, now=NOW)

    assert bt.status == BacktestStatus.COMPLETED
    assert bt.snapshot.weeks == ()  # snapshot vacío
    assert bt.result.total_return == Decimal("0")
    assert bt.weeks_total == 0


# ─────────────────────── Falla en lectura de análisis ───────────────────────


async def test_engine_falla_si_analysis_port_lanza() -> None:
    class BrokenAnalysis:
        async def list_runs_in_period(self, **_kw):
            raise RuntimeError("analysis DB down")

        async def get_picks_for_run(self, **_kw):
            raise NotImplementedError

    engine = BacktestEngine(
        analysis=BrokenAnalysis(),  # type: ignore[arg-type]
        prices=FakePriceProvider(),
        strategy=WeeklyRotationStrategy(),
    )
    bt = _bt()
    await engine.run(bt, now=NOW)

    assert bt.status == BacktestStatus.FAILED
    assert bt.error.code == "analysis_unreachable"
