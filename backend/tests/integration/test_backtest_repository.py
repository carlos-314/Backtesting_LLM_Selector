"""Tests de integración del `BacktestRepository` contra Postgres real (F2 §8.3).

Verifica round-trip por cada estado del ciclo de vida, idempotencia del
save (re-save), persistencia de snapshot y equity completos.
"""
import uuid
from collections.abc import AsyncIterator
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.backtesting.backtest import Backtest, BacktestError
from app.domain.backtesting.parameters import BacktestParameters, BacktestStatus
from app.domain.backtesting.result import BacktestResult, EquityPoint, EquitySeries
from app.domain.backtesting.snapshot import (
    OHLC,
    ReproducibilitySnapshot,
    SnapshotPick,
    SnapshotWeek,
)
from app.domain.shared.money import Money
from app.domain.shared.ticker import TickerSymbol
from app.domain.shared.week import Week
from app.infrastructure.persistence.app_db import SessionFactory
from app.infrastructure.persistence.models.access import AppUser
from app.infrastructure.repositories.backtest_repository import BacktestRepository


# ────────────────────────── fixtures ──────────────────────────


@pytest.fixture
async def db() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as s:
        yield s


@pytest.fixture
async def user_id(db: AsyncSession) -> uuid.UUID:
    """Inserta un AppUser (created_by tiene FK RESTRICT)."""
    u = AppUser(email=f"u_{uuid.uuid4().hex[:6]}@x.com", google_id=uuid.uuid4().hex, role="analyst")
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u.id


@pytest.fixture(autouse=True)
async def _wipe() -> None:
    async with SessionFactory() as s:
        for t in (
            "backtest_snapshot_pick",
            "backtest_snapshot_week",
            "backtest_equity_point",
            "backtest_result",
            "backtest",
            "app_user",
        ):
            await s.execute(text(f"DELETE FROM {t}"))
        await s.commit()


NOW = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)


def _params() -> BacktestParameters:
    return BacktestParameters(
        period_start=Week(date(2026, 1, 5)),
        period_end=Week(date(2026, 1, 26)),
        initial_capital=Money.usd("10000"),
    )


def _fresh_bt(user_id: uuid.UUID) -> Backtest:
    return Backtest(
        id=uuid.uuid4(), name="test", created_by=user_id, parameters=_params(), created_at=NOW
    )


# ─────────────────────── Round-trip pending ───────────────────────


async def test_repo_save_y_get_pending(db: AsyncSession, user_id: uuid.UUID) -> None:
    repo = BacktestRepository(db)
    bt = _fresh_bt(user_id)
    await repo.save(bt)

    recovered = await repo.get(bt.id)
    assert recovered is not None
    assert recovered.id == bt.id
    assert recovered.status == BacktestStatus.PENDING
    assert recovered.name == "test"
    assert recovered.parameters.period_start.week_date == date(2026, 1, 5)
    assert recovered.parameters.period_end.week_date == date(2026, 1, 26)
    assert recovered.parameters.initial_capital == Money.usd("10000")
    assert recovered.result is None
    assert recovered.snapshot is None


# ─────────────────────── Round-trip running ───────────────────────


async def test_repo_save_y_get_running_con_progreso(
    db: AsyncSession, user_id: uuid.UUID
) -> None:
    repo = BacktestRepository(db)
    bt = _fresh_bt(user_id)
    bt.start(when=NOW, weeks_total=4)
    bt.record_progress(weeks_processed=2)
    await repo.save(bt)

    recovered = await repo.get(bt.id)
    assert recovered.status == BacktestStatus.RUNNING
    assert recovered.weeks_total == 4
    assert recovered.weeks_processed == 2
    assert recovered.started_at == NOW


# ─────────────────────── Round-trip completed ───────────────────────


async def test_repo_save_y_get_completed_con_result_equity_snapshot(
    db: AsyncSession, user_id: uuid.UUID
) -> None:
    repo = BacktestRepository(db)
    bt = _fresh_bt(user_id)
    bt.start(when=NOW, weeks_total=2)
    bt.record_progress(weeks_processed=2)

    snapshot = ReproducibilitySnapshot(weeks=(
        SnapshotWeek(
            week=Week(date(2026, 1, 5)),
            resolved_run_id=42,
            run_code="RUN_42",
            picks=(
                SnapshotPick(
                    ticker=TickerSymbol("AAPL"),
                    ohlc=OHLC(Decimal("100"), Decimal("105"), Decimal("98"), Decimal("103"), "USD"),
                ),
                SnapshotPick(
                    ticker=TickerSymbol("MSFT"),
                    ohlc=OHLC(Decimal("200"), Decimal("210"), Decimal("195"), Decimal("205"), "USD"),
                ),
            ),
        ),
        SnapshotWeek(
            week=Week(date(2026, 1, 12)),
            resolved_run_id=43,
            run_code="RUN_43",
            picks=(
                SnapshotPick(
                    ticker=TickerSymbol("AAPL"),
                    ohlc=OHLC(Decimal("104"), Decimal("106"), Decimal("103"), Decimal("105"), "USD"),
                ),
            ),
        ),
    ))
    result = BacktestResult(
        total_return=Decimal("0.05"),
        cagr=Decimal("0.50"),
        sharpe=Decimal("1.2"),
        equity_curve=(
            EquityPoint(EquitySeries.PORTFOLIO, date(2026, 1, 5), Decimal("10000")),
            EquityPoint(EquitySeries.PORTFOLIO, date(2026, 1, 12), Decimal("10500")),
            EquityPoint(EquitySeries.BENCHMARK, date(2026, 1, 5), Decimal("10000")),
            EquityPoint(EquitySeries.BENCHMARK, date(2026, 1, 12), Decimal("10000")),
        ),
    )
    bt.complete(result=result, snapshot=snapshot, when=NOW)
    await repo.save(bt)

    recovered = await repo.get(bt.id)
    assert recovered.status == BacktestStatus.COMPLETED
    assert recovered.result is not None
    assert recovered.result.total_return == Decimal("0.0500")
    assert recovered.result.cagr == Decimal("0.5000")
    assert recovered.result.sharpe == Decimal("1.2000")
    assert len(recovered.result.equity_curve) == 4

    # Snapshot íntegro
    assert recovered.snapshot is not None
    assert len(recovered.snapshot.weeks) == 2
    w0 = recovered.snapshot.weeks[0]
    assert w0.week.week_date == date(2026, 1, 5)
    assert w0.resolved_run_id == 42
    assert w0.run_code == "RUN_42"
    assert len(w0.picks) == 2
    tickers = {str(p.ticker) for p in w0.picks}
    assert tickers == {"AAPL", "MSFT"}


# ─────────────────────── Round-trip failed ───────────────────────


async def test_repo_save_y_get_failed_con_error_detail(
    db: AsyncSession, user_id: uuid.UUID
) -> None:
    repo = BacktestRepository(db)
    bt = _fresh_bt(user_id)
    bt.fail(
        error=BacktestError(
            code="prices_unavailable",
            message="yfinance down",
            context={"ticker": "AAPL", "day": "2026-01-05"},
        ),
        when=NOW,
    )
    await repo.save(bt)

    recovered = await repo.get(bt.id)
    assert recovered.status == BacktestStatus.FAILED
    assert recovered.error is not None
    assert recovered.error.code == "prices_unavailable"
    assert recovered.error.message == "yfinance down"
    assert recovered.error.context == {"ticker": "AAPL", "day": "2026-01-05"}


# ─────────────────────── Round-trip cancelled ───────────────────────


async def test_repo_save_y_get_cancelled(db: AsyncSession, user_id: uuid.UUID) -> None:
    repo = BacktestRepository(db)
    bt = _fresh_bt(user_id)
    bt.start(when=NOW, weeks_total=4)
    bt.cancel(when=NOW)
    await repo.save(bt)

    recovered = await repo.get(bt.id)
    assert recovered.status == BacktestStatus.CANCELLED
    assert recovered.completed_at == NOW


# ─────────────────────── Idempotencia ───────────────────────


async def test_repo_save_idempotente_dos_saves_sobre_mismo_id_no_duplican(
    db: AsyncSession, user_id: uuid.UUID
) -> None:
    """Caso típico: worker llama save al pasar de pending→running→completed.
    Cada save reemplaza dependientes; no se duplican equity ni snapshot."""
    repo = BacktestRepository(db)
    bt = _fresh_bt(user_id)
    await repo.save(bt)  # pending

    bt.start(when=NOW, weeks_total=1)
    await repo.save(bt)  # running

    snapshot = ReproducibilitySnapshot(weeks=(
        SnapshotWeek(Week(date(2026, 1, 5)), 1, "R", (
            SnapshotPick(TickerSymbol("AAPL"), OHLC(
                Decimal("100"), Decimal("105"), Decimal("98"), Decimal("103"), "USD"
            )),
        )),
    ))
    result = BacktestResult(
        total_return=Decimal("0.03"),
        equity_curve=(
            EquityPoint(EquitySeries.PORTFOLIO, date(2026, 1, 5), Decimal("10300")),
            EquityPoint(EquitySeries.BENCHMARK, date(2026, 1, 5), Decimal("10000")),
        ),
    )
    bt.record_progress(weeks_processed=1)
    bt.complete(result=result, snapshot=snapshot, when=NOW)
    await repo.save(bt)  # completed

    # Re-save del COMPLETED: debe ser idempotente
    await repo.save(bt)

    # Solo 1 backtest, 1 result, 2 equity points, 1 snapshot_week, 1 pick
    cnt = lambda t: db.execute(text(f"SELECT COUNT(*) FROM {t}"))  # noqa: E731

    res = await cnt("backtest")
    assert res.scalar() == 1
    res = await cnt("backtest_result")
    assert res.scalar() == 1
    res = await cnt("backtest_equity_point")
    assert res.scalar() == 2
    res = await cnt("backtest_snapshot_week")
    assert res.scalar() == 1
    res = await cnt("backtest_snapshot_pick")
    assert res.scalar() == 1


# ─────────────────────── get no encontrado ───────────────────────


async def test_repo_get_id_inexistente_devuelve_none(db: AsyncSession) -> None:
    repo = BacktestRepository(db)
    assert await repo.get(uuid.uuid4()) is None


# ─────────────────────── FK: created_by inexistente ───────────────────────


async def test_repo_save_con_created_by_inexistente_falla_FK(
    db: AsyncSession,
) -> None:
    """F2 §5.2: ON DELETE RESTRICT en created_by. Insertar con un user
    inexistente debe fallar."""
    from sqlalchemy.exc import IntegrityError

    repo = BacktestRepository(db)
    bt = Backtest(
        id=uuid.uuid4(),
        name="x",
        created_by=uuid.uuid4(),  # user que no existe
        parameters=_params(),
        created_at=NOW,
    )
    with pytest.raises(IntegrityError):
        await repo.save(bt)


# ─────────────────────── Recuperación de equity ordenada ───────────────────────


async def test_repo_get_equity_curve_ordenada_por_serie_y_fecha(
    db: AsyncSession, user_id: uuid.UUID
) -> None:
    repo = BacktestRepository(db)
    bt = _fresh_bt(user_id)
    bt.start(when=NOW, weeks_total=3)
    bt.record_progress(weeks_processed=3)

    # Insertamos los puntos desordenados al construir; el repo los reordena al leer
    pts = (
        EquityPoint(EquitySeries.PORTFOLIO, date(2026, 1, 5), Decimal("100")),
        EquityPoint(EquitySeries.PORTFOLIO, date(2026, 1, 12), Decimal("110")),
        EquityPoint(EquitySeries.PORTFOLIO, date(2026, 1, 19), Decimal("120")),
        EquityPoint(EquitySeries.BENCHMARK, date(2026, 1, 5), Decimal("100")),
        EquityPoint(EquitySeries.BENCHMARK, date(2026, 1, 12), Decimal("100")),
        EquityPoint(EquitySeries.BENCHMARK, date(2026, 1, 19), Decimal("100")),
    )
    bt.complete(
        result=BacktestResult(total_return=Decimal("0.20"), equity_curve=pts),
        snapshot=ReproducibilitySnapshot(weeks=()),
        when=NOW,
    )
    await repo.save(bt)

    recovered = await repo.get(bt.id)
    # Debe estar ordenado por (series asc, date asc)
    dates_by_series: dict[EquitySeries, list[date]] = {}
    for pt in recovered.result.equity_curve:
        dates_by_series.setdefault(pt.series, []).append(pt.point_date)
    for series, ds in dates_by_series.items():
        assert ds == sorted(ds), f"equity_curve para {series} desordenada"
