"""Tests de integración del schema F2 §5 contra Postgres real (F2 §8.3).

Lo que se prueba aquí NO se puede demostrar con mocks: constraints, CHECKs,
índices UNIQUE, ON DELETE CASCADE/RESTRICT. Es el caso de "el valor está en
el detalle que un mock no captura" (F2 §8.5).

Requisitos:
- Postgres local levantado: `docker compose up -d postgres`.
- Migración aplicada: `alembic upgrade head`.
"""
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.app_db import SessionFactory
from app.infrastructure.persistence.models import (
    AppUser,
    Backtest,
    BacktestEquityPoint,
    BacktestResult,
    BacktestSnapshotPick,
    BacktestSnapshotWeek,
    FxDaily,
    PriceCacheDaily,
)

# ───────────────────────────── helpers ─────────────────────────────


@pytest.fixture
async def db() -> AsyncSession:
    async with SessionFactory() as s:
        yield s


@pytest.fixture(autouse=True)
async def _wipe_data() -> None:
    """Borra los datos entre tests (no las tablas) en orden FK-safe."""
    async with SessionFactory() as s:
        for table in (
            "backtest_snapshot_pick",
            "backtest_snapshot_week",
            "backtest_equity_point",
            "backtest_result",
            "backtest",
            "fx_daily",
            "price_cache_daily",
            "app_user",
        ):
            await s.execute(text(f"DELETE FROM {table}"))
        await s.commit()


def _user(role: str = "analyst", suffix: str = "") -> AppUser:
    sfx = suffix or uuid.uuid4().hex[:6]
    return AppUser(
        email=f"u_{sfx}@example.com",
        google_id=f"g_{sfx}",
        full_name="Test",
        role=role,
    )


def _backtest(user_id: uuid.UUID, **overrides) -> Backtest:
    from sqlalchemy.dialects.postgresql.ranges import Range

    return Backtest(
        created_by=user_id,
        name=overrides.pop("name", "BT"),
        status=overrides.pop("status", "pending"),
        period=overrides.pop("period", Range(date(2026, 1, 5), date(2026, 6, 1), bounds="[)")),
        initial_capital=overrides.pop("initial_capital", Decimal("100000.00")),
        base_currency=overrides.pop("base_currency", "USD"),
        strategy_code=overrides.pop("strategy_code", "weekly_rotation"),
        benchmark_code=overrides.pop("benchmark_code", "buy_and_hold"),
        **overrides,
    )


# ────────────────────────── CHECK constraints ──────────────────────────


async def test_app_user_role_rechaza_valor_fuera_del_enum(db: AsyncSession) -> None:
    db.add(_user(role="hacker"))
    with pytest.raises(IntegrityError, match="ck_app_user_role"):
        await db.commit()


async def test_app_user_role_acepta_los_tres_valores_validos(db: AsyncSession) -> None:
    for role in ("viewer", "analyst", "admin"):
        db.add(_user(role=role, suffix=role))
    await db.commit()
    res = await db.execute(select(AppUser))
    assert len(res.scalars().all()) == 3


async def test_backtest_status_rechaza_valor_fuera_del_enum(db: AsyncSession) -> None:
    u = _user()
    db.add(u)
    await db.flush()
    db.add(_backtest(u.id, status="zombie"))
    with pytest.raises(IntegrityError, match="ck_backtest_status"):
        await db.commit()


async def test_backtest_initial_capital_rechaza_cero_o_negativo(db: AsyncSession) -> None:
    u = _user()
    db.add(u)
    await db.flush()
    db.add(_backtest(u.id, initial_capital=Decimal("0.00")))
    with pytest.raises(IntegrityError, match="ck_backtest_initial_capital_positive"):
        await db.commit()


async def test_backtest_period_rechaza_rango_vacio(db: AsyncSession) -> None:
    from sqlalchemy.dialects.postgresql.ranges import Range

    u = _user()
    db.add(u)
    await db.flush()
    # Rango vacío: [d, d) — Postgres lo considera empty.
    db.add(_backtest(u.id, period=Range(date(2026, 1, 1), date(2026, 1, 1), bounds="[)")))
    with pytest.raises(IntegrityError, match="ck_backtest_period_not_empty"):
        await db.commit()


async def test_equity_point_series_rechaza_valor_fuera_del_enum(db: AsyncSession) -> None:
    u = _user()
    db.add(u)
    await db.flush()
    bt = _backtest(u.id)
    db.add(bt)
    await db.flush()
    db.add(BacktestEquityPoint(
        backtest_id=bt.id, series="invalid", point_date=date(2026, 1, 5), value=Decimal("100.00")
    ))
    with pytest.raises(IntegrityError, match="ck_equity_point_series"):
        await db.commit()


# ────────────────────────── UNIQUE constraints ──────────────────────────


async def test_app_user_email_es_unique(db: AsyncSession) -> None:
    db.add(_user(suffix="a"))
    await db.commit()
    db.add(AppUser(email="u_a@example.com", google_id="g_other", role="analyst"))
    with pytest.raises(IntegrityError):
        await db.commit()


async def test_app_user_google_id_es_nullable_adr0006(db: AsyncSession) -> None:
    """ADR-0006: pre-alta por admin debe poder dejar google_id sin vincular."""
    db.add(AppUser(email="pre_alta@x.com", google_id=None, role="analyst"))
    await db.commit()
    res = await db.execute(
        select(AppUser).where(AppUser.email == "pre_alta@x.com")
    )
    user = res.scalar_one()
    assert user.google_id is None
    assert user.role == "analyst"


async def test_app_user_google_id_sigue_siendo_unique_tras_nullable(
    db: AsyncSession,
) -> None:
    """ADR-0006: UNIQUE se conserva; dos rows no pueden compartir google_id."""
    db.add(AppUser(email="a@x.com", google_id="shared", role="analyst"))
    await db.commit()
    db.add(AppUser(email="b@x.com", google_id="shared", role="viewer"))
    with pytest.raises(IntegrityError):
        await db.commit()


async def test_equity_point_backtest_series_date_es_unique(db: AsyncSession) -> None:
    u = _user()
    db.add(u)
    await db.flush()
    bt = _backtest(u.id)
    db.add(bt)
    await db.flush()
    db.add(BacktestEquityPoint(
        backtest_id=bt.id, series="portfolio", point_date=date(2026, 1, 5), value=Decimal("100")
    ))
    await db.commit()
    db.add(BacktestEquityPoint(
        backtest_id=bt.id, series="portfolio", point_date=date(2026, 1, 5), value=Decimal("999")
    ))
    with pytest.raises(IntegrityError, match="uq_equity_point_backtest_series_date"):
        await db.commit()


async def test_price_cache_ticker_date_es_unique(db: AsyncSession) -> None:
    db.add(PriceCacheDaily(
        ticker="AAPL", price_date=date(2026, 1, 5), close=Decimal("150"), currency="USD"
    ))
    await db.commit()
    db.add(PriceCacheDaily(
        ticker="AAPL", price_date=date(2026, 1, 5), close=Decimal("151"), currency="USD"
    ))
    with pytest.raises(IntegrityError, match="uq_price_cache_ticker_date"):
        await db.commit()


async def test_fx_daily_pair_date_es_unique(db: AsyncSession) -> None:
    db.add(FxDaily(pair="EUR/USD", date=date(2026, 1, 5), rate=Decimal("1.08")))
    await db.commit()
    db.add(FxDaily(pair="EUR/USD", date=date(2026, 1, 5), rate=Decimal("1.09")))
    with pytest.raises(IntegrityError, match="uq_fx_daily_pair_date"):
        await db.commit()


# ─────────────────────── ON DELETE CASCADE / RESTRICT ───────────────────────


async def test_borrar_app_user_con_backtests_es_restringido(db: AsyncSession) -> None:
    """F2 §5.2: created_by tiene ON DELETE RESTRICT para proteger trazabilidad."""
    u = _user()
    db.add(u)
    await db.flush()
    db.add(_backtest(u.id))
    await db.commit()

    with pytest.raises(IntegrityError):
        await db.execute(text("DELETE FROM app_user WHERE id = :uid").bindparams(uid=u.id))
        await db.commit()


async def test_borrar_backtest_cascada_a_result_equity_y_snapshot(db: AsyncSession) -> None:
    """F2 §5.2/§5.3: ON DELETE CASCADE en todas las tablas dependientes."""
    u = _user()
    db.add(u)
    await db.flush()
    bt = _backtest(u.id, status="completed")
    db.add(bt)
    await db.flush()

    db.add(BacktestResult(backtest_id=bt.id, total_return=Decimal("0.15")))
    db.add(BacktestEquityPoint(
        backtest_id=bt.id, series="portfolio", point_date=date(2026, 1, 5), value=Decimal("100")
    ))
    sw = BacktestSnapshotWeek(
        backtest_id=bt.id, week_date=date(2026, 1, 5), resolved_run_id=42, run_code="RUN_X"
    )
    db.add(sw)
    await db.flush()
    db.add(BacktestSnapshotPick(
        snapshot_week_id=sw.id,
        ticker="AAPL",
        open=Decimal("1"), high=Decimal("2"), low=Decimal("0.5"), close=Decimal("1.5"),
    ))
    await db.commit()

    await db.execute(text("DELETE FROM backtest WHERE id = :bid").bindparams(bid=bt.id))
    await db.commit()

    for model in (BacktestResult, BacktestEquityPoint, BacktestSnapshotWeek, BacktestSnapshotPick):
        res = await db.execute(select(model))
        assert res.scalars().first() is None, f"{model.__tablename__} no cascadeó"


# ───────────────────── Defaults y nulables esperados ─────────────────────


async def test_app_user_is_active_default_true(db: AsyncSession) -> None:
    u = AppUser(email="def@example.com", google_id="g_def", role="viewer")
    db.add(u)
    await db.commit()
    await db.refresh(u)
    assert u.is_active is True


async def test_backtest_base_currency_default_usd(db: AsyncSession) -> None:
    u = _user()
    db.add(u)
    await db.flush()
    bt = Backtest(
        created_by=u.id,
        name="defaults",
        status="pending",
        period=__import__("sqlalchemy.dialects.postgresql.ranges", fromlist=["Range"]).Range(
            date(2026, 1, 5), date(2026, 6, 1), bounds="[)"
        ),
        initial_capital=Decimal("1000.00"),
        strategy_code="weekly_rotation",
        benchmark_code="buy_and_hold",
    )
    db.add(bt)
    await db.commit()
    await db.refresh(bt)
    assert bt.base_currency == "USD"


async def test_price_cache_source_default_yfinance(db: AsyncSession) -> None:
    p = PriceCacheDaily(ticker="MSFT", price_date=date(2026, 1, 5), currency="USD")
    db.add(p)
    await db.commit()
    await db.refresh(p)
    assert p.source == "yfinance"


# ─────────────────────── Snapshot sin FK a análisis ───────────────────────


async def test_snapshot_week_acepta_resolved_run_id_arbitrario(db: AsyncSession) -> None:
    """F2 §5.3: resolved_run_id es una copia, no FK. Acepta cualquier int positivo."""
    u = _user()
    db.add(u)
    await db.flush()
    bt = _backtest(u.id)
    db.add(bt)
    await db.flush()
    db.add(BacktestSnapshotWeek(
        backtest_id=bt.id, week_date=date(2026, 1, 5), resolved_run_id=999999, run_code="ANY"
    ))
    await db.commit()  # No falla, no hay FK contra base de análisis.
