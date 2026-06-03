"""Integración del workflow `run_backtest` invocando la tarea directamente.

No depende de arq runtime ni de Redis: invoca `run_backtest(ctx, id)` como
una función async normal, pasándole un cliente yfinance falso.

Estos tests son la prueba end-to-end más completa del backend día uno:
ACL real + repo real + caché real + dominio puro, con yfinance mockeado
(F2 §8.5).
"""
import uuid
from collections.abc import AsyncIterator
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.domain.backtesting.backtest import Backtest, BacktestError
from app.domain.backtesting.parameters import BacktestParameters, BacktestStatus
from app.domain.shared.money import Money
from app.domain.shared.week import NEW_YORK, Week
from app.infrastructure.persistence.app_db import SessionFactory
from app.infrastructure.persistence.models.access import AppUser
from app.infrastructure.repositories.backtest_repository import BacktestRepository
from app.jobs.run_backtest import run_backtest

from tests.integration.fake_yfinance import FakeYfinanceClient
from app.infrastructure.price_provider.yfinance_client import OHLCRow

# Reutilizamos las URLs y DDL de los otros tests de integración
ANALYSIS_TEST_URL = (
    "postgresql+asyncpg://backtesting:backtesting_dev@localhost:55432/backtesting_analysis_test"
)

NOW = datetime(2026, 2, 1, tzinfo=timezone.utc)


def _ohlc_row(o="100", c="103") -> OHLCRow:
    op = Decimal(o)
    cl = Decimal(c)
    return OHLCRow(
        open=op,
        high=max(op, cl),
        low=min(op, cl),
        close=cl,
        adj_close=cl,
        volume=1_000_000,
        currency="USD",
    )


# ─────────────────────────── fixtures ───────────────────────────


@pytest.fixture(autouse=True)
async def _wipe_app() -> None:
    async with SessionFactory() as s:
        for t in (
            "backtest_snapshot_pick", "backtest_snapshot_week",
            "backtest_equity_point", "backtest_result", "backtest",
            "price_cache_daily", "fx_daily", "app_user",
        ):
            await s.execute(text(f"DELETE FROM {t}"))
        await s.commit()


@pytest.fixture(autouse=True)
async def _setup_analysis() -> AsyncIterator[None]:
    """Crea schema legacy en analysis_test y lo puebla con runs+picks."""
    engine = create_async_engine(ANALYSIS_TEST_URL, echo=False)
    SessionMaker = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        for stmt in (
            "DROP TABLE IF EXISTS portfolios",
            "DROP TABLE IF EXISTS analysis_runs",
            """
            CREATE TABLE analysis_runs (
                id_run        integer PRIMARY KEY,
                "fechaRun"    timestamp with time zone,
                run_code      character varying(20),
                descripcion   text,
                status        character varying(50) DEFAULT 'STARTED'
            )
            """,
            """
            CREATE TABLE portfolios (
                id_portfolio  integer PRIMARY KEY,
                id_run        integer,
                ticker        character varying(20),
                nombre        text,
                rol           text
            )
            """,
        ):
            await conn.execute(text(stmt))

    async with SessionMaker() as s:
        # 2 runs OK, 1 ticker cada uno (AAPL semana 5, AAPL semana 12)
        await s.execute(text(
            'INSERT INTO analysis_runs (id_run, "fechaRun", run_code, status)'
            " VALUES (1, :d1, 'R1', 'COMPLETED'), (2, :d2, 'R2', 'COMPLETED')"
        ), {
            "d1": datetime(2026, 1, 5, 9, 0, tzinfo=NEW_YORK),
            "d2": datetime(2026, 1, 12, 9, 0, tzinfo=NEW_YORK),
        })
        await s.execute(text(
            "INSERT INTO portfolios (id_portfolio, id_run, ticker)"
            " VALUES (1, 1, 'AAPL'), (2, 2, 'AAPL')"
        ))
        await s.commit()

    yield
    await engine.dispose()


# We need to monkeypatch the SessionFactory of analysis to point to the test DB.
@pytest.fixture(autouse=True)
def _redirect_analysis_session_factory(monkeypatch) -> None:
    test_engine = create_async_engine(ANALYSIS_TEST_URL, echo=False)
    test_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    # `run_backtest` importa `AnalysisSessionFactory` de analysis_db.
    monkeypatch.setattr(
        "app.jobs.run_backtest.AnalysisSessionFactory", test_factory
    )


@pytest.fixture
async def user_id() -> uuid.UUID:
    async with SessionFactory() as s:
        u = AppUser(email="u@x.com", google_id="g", role="analyst")
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return u.id


def _params() -> BacktestParameters:
    return BacktestParameters(
        period_start=Week(date(2026, 1, 5)),
        period_end=Week(date(2026, 1, 12)),
        initial_capital=Money.usd("10000"),
    )


# ─────────────────────── Flujo feliz ───────────────────────


async def test_run_backtest_pasa_pending_a_completed(user_id: uuid.UUID) -> None:
    yf = FakeYfinanceClient()
    yf.set_ohlc("AAPL", date(2026, 1, 5), _ohlc_row(c="100"))
    yf.set_ohlc("AAPL", date(2026, 1, 12), _ohlc_row(c="110"))

    bt = Backtest(id=uuid.uuid4(), name="T", created_by=user_id, parameters=_params(), created_at=NOW)
    async with SessionFactory() as s:
        await BacktestRepository(s).save(bt)

    await run_backtest({}, bt.id, yfinance_client=yf)

    async with SessionFactory() as s:
        recovered = await BacktestRepository(s).get(bt.id)
    assert recovered is not None
    assert recovered.status == BacktestStatus.COMPLETED
    assert recovered.result is not None
    assert recovered.snapshot is not None
    assert len(recovered.snapshot.weeks) == 2


# ─────────────────────── Cancelación cooperativa ───────────────────────


async def test_run_backtest_detecta_cancelacion_de_la_bbdd_y_termina_cancelled(
    user_id: uuid.UUID,
) -> None:
    """F2 §6.5: el endpoint cancel marca cancelled en BBDD; el worker lo ve
    entre semanas y aborta dejando el backtest cancelado."""
    yf = FakeYfinanceClient()
    yf.set_ohlc("AAPL", date(2026, 1, 5), _ohlc_row())
    yf.set_ohlc("AAPL", date(2026, 1, 12), _ohlc_row())

    bt = Backtest(id=uuid.uuid4(), name="T", created_by=user_id, parameters=_params(), created_at=NOW)
    async with SessionFactory() as s:
        await BacktestRepository(s).save(bt)

    # Simulamos que el endpoint cancela MIENTRAS el worker está procesando:
    # marcamos cancelled en BBDD ANTES de ejecutar run_backtest. La 1ª
    # iteración del bucle de semanas detectará la flag y abortará.
    async with SessionFactory() as s:
        bt_db = await BacktestRepository(s).get(bt.id)
        bt_db.cancel(when=NOW)
        await BacktestRepository(s).save(bt_db)

    await run_backtest({}, bt.id, yfinance_client=yf)

    async with SessionFactory() as s:
        recovered = await BacktestRepository(s).get(bt.id)
    assert recovered.status == BacktestStatus.CANCELLED


# ─────────────────────── Idempotencia + estados no pending ───────────────────────


async def test_run_backtest_id_inexistente_no_lanza(user_id: uuid.UUID) -> None:
    """Si arq encola un id que no existe (race con borrado por algún
    proceso), la tarea se loguea y termina sin error."""
    yf = FakeYfinanceClient()
    await run_backtest({}, uuid.uuid4(), yfinance_client=yf)  # no asserts: simplemente no debe lanzar


async def test_run_backtest_de_un_bt_ya_completed_no_re_ejecuta(
    user_id: uuid.UUID,
) -> None:
    """Defensa contra re-enqueues accidentales: si el bt ya está terminal,
    la tarea no hace nada."""
    bt = Backtest(id=uuid.uuid4(), name="T", created_by=user_id, parameters=_params(), created_at=NOW)
    bt.fail(error=BacktestError(code="x", message="y"), when=NOW)
    async with SessionFactory() as s:
        await BacktestRepository(s).save(bt)

    yf = FakeYfinanceClient()
    await run_backtest({}, bt.id, yfinance_client=yf)
    # No debe haber llamado a yfinance ni cambiado el estado
    assert yf.fetch_ohlc_calls == []

    async with SessionFactory() as s:
        recovered = await BacktestRepository(s).get(bt.id)
    assert recovered.status == BacktestStatus.FAILED
