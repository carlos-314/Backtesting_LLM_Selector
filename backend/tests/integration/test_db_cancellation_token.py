"""Integración del `DbCancellationToken` (F2 §6.5)."""
import uuid
from collections.abc import AsyncIterator
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.backtesting.backtest import Backtest
from app.domain.backtesting.parameters import BacktestParameters
from app.domain.shared.money import Money
from app.domain.shared.week import Week
from app.infrastructure.persistence.app_db import SessionFactory
from app.infrastructure.persistence.models.access import AppUser
from app.infrastructure.repositories.backtest_repository import BacktestRepository
from app.infrastructure.repositories.db_cancellation_token import DbCancellationToken


@pytest.fixture
async def db() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as s:
        yield s


@pytest.fixture(autouse=True)
async def _wipe() -> None:
    async with SessionFactory() as s:
        for t in (
            "backtest_snapshot_pick", "backtest_snapshot_week",
            "backtest_equity_point", "backtest_result", "backtest", "app_user",
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


async def test_token_devuelve_false_cuando_bt_no_existe(db: AsyncSession) -> None:
    token = DbCancellationToken(db, uuid.uuid4())
    assert await token.is_cancelled() is False


async def test_token_devuelve_false_cuando_bt_esta_pending(db: AsyncSession) -> None:
    u = AppUser(email="u@x.com", google_id="g", role="analyst")
    db.add(u)
    await db.commit()
    await db.refresh(u)

    bt = Backtest(id=uuid.uuid4(), name="x", created_by=u.id, parameters=_params(), created_at=NOW)
    await BacktestRepository(db).save(bt)

    token = DbCancellationToken(db, bt.id)
    assert await token.is_cancelled() is False


async def test_token_devuelve_true_cuando_bt_pasa_a_cancelled(db: AsyncSession) -> None:
    """Caso clave: el endpoint cancela el bt, el worker lo detecta vía token."""
    u = AppUser(email="u@x.com", google_id="g", role="analyst")
    db.add(u)
    await db.commit()
    await db.refresh(u)

    bt = Backtest(id=uuid.uuid4(), name="x", created_by=u.id, parameters=_params(), created_at=NOW)
    repo = BacktestRepository(db)
    await repo.save(bt)

    token = DbCancellationToken(db, bt.id)
    assert await token.is_cancelled() is False  # antes de cancelar

    # Simula lo que hace el endpoint /cancel
    bt.cancel(when=NOW)
    await repo.save(bt)

    assert await token.is_cancelled() is True


async def test_token_devuelve_false_para_otros_estados_terminales(
    db: AsyncSession,
) -> None:
    """COMPLETED/FAILED no son cancelled; el token solo dispara para cancelled."""
    from app.domain.backtesting.backtest import BacktestError

    u = AppUser(email="u@x.com", google_id="g", role="analyst")
    db.add(u)
    await db.commit()
    await db.refresh(u)

    bt = Backtest(id=uuid.uuid4(), name="x", created_by=u.id, parameters=_params(), created_at=NOW)
    bt.fail(error=BacktestError(code="x", message="y"), when=NOW)
    await BacktestRepository(db).save(bt)

    assert await DbCancellationToken(db, bt.id).is_cancelled() is False
