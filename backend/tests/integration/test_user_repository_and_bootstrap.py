"""Integración del `SqlUserRepository` + `BootstrapInitialAdmin` contra
Postgres real (F2 §8.3, ADR-0006)."""
import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.access.bootstrap_admin import BootstrapInitialAdmin
from app.application.access.register_user import RegisterUser
from app.domain.access.role import Role
from app.domain.access.user import User
from app.infrastructure.persistence.app_db import SessionFactory
from app.infrastructure.repositories.user_repository import SqlUserRepository


@pytest.fixture
async def db() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as s:
        yield s


@pytest.fixture(autouse=True)
async def _wipe() -> None:
    async with SessionFactory() as s:
        # Orden FK-safe: dependientes de backtest primero (CASCADE → snapshot_pick),
        # luego backtest, luego app_user (RESTRICT desde backtest.created_by).
        for t in (
            "backtest_snapshot_pick", "backtest_snapshot_week",
            "backtest_equity_point", "backtest_result", "backtest",
            "app_user",
        ):
            await s.execute(text(f"DELETE FROM {t}"))
        await s.commit()


# ─────────────────── CRUD básico ───────────────────


async def test_save_y_find_by_id(db: AsyncSession) -> None:
    repo = SqlUserRepository(db)
    user = User(
        id=uuid.uuid4(),
        email="u@x.com",
        role=Role.ANALYST,
        google_id="g1",
    )
    await repo.save(user)

    got = await repo.find_by_id(user.id)
    assert got is not None and got.email == "u@x.com" and got.role == Role.ANALYST


async def test_find_by_email_devuelve_pre_alta_con_google_id_null(
    db: AsyncSession,
) -> None:
    """ADR-0006: la pre-alta tiene google_id=None y se busca por email."""
    repo = SqlUserRepository(db)
    pre = User(
        id=uuid.uuid4(),
        email="pre@x.com",
        role=Role.ANALYST,
        google_id=None,
    )
    await repo.save(pre)

    got = await repo.find_by_email("pre@x.com")
    assert got is not None and got.google_id is None


async def test_find_by_google_id_devuelve_user_vinculado(db: AsyncSession) -> None:
    repo = SqlUserRepository(db)
    user = User(id=uuid.uuid4(), email="u@x.com", role=Role.VIEWER, google_id="gXYZ")
    await repo.save(user)
    got = await repo.find_by_google_id("gXYZ")
    assert got is not None and got.email == "u@x.com"


async def test_find_by_google_id_no_existe_devuelve_none(db: AsyncSession) -> None:
    assert await SqlUserRepository(db).find_by_google_id("ghost") is None


async def test_link_google_id_actualiza_pre_alta(db: AsyncSession) -> None:
    """Flujo de primer login: pre-alta sin google_id → link → vinculado."""
    repo = SqlUserRepository(db)
    pre = User(id=uuid.uuid4(), email="pre@x.com", role=Role.VIEWER, google_id=None)
    await repo.save(pre)

    await repo.link_google_id(pre.id, "g_freshly_linked")

    refreshed = await repo.find_by_id(pre.id)
    assert refreshed.google_id == "g_freshly_linked"


async def test_list_all_devuelve_todos_en_orden_creacion(db: AsyncSession) -> None:
    repo = SqlUserRepository(db)
    for i in range(3):
        await repo.save(User(
            id=uuid.uuid4(),
            email=f"u{i}@x.com",
            role=Role.VIEWER,
            google_id=f"g{i}",
        ))
    all_users = await repo.list_all()
    assert len(all_users) == 3


# ─────────────────── Bootstrap admin ───────────────────


async def test_bootstrap_crea_admin_si_tabla_vacia_en_db_real(
    db: AsyncSession,
) -> None:
    repo = SqlUserRepository(db)
    bootstrap = BootstrapInitialAdmin(repo)

    created = await bootstrap("carlos.picazo.314@gmail.com")
    assert created is not None and created.role == Role.ADMIN

    persisted = await repo.find_by_email("carlos.picazo.314@gmail.com")
    assert persisted is not None
    assert persisted.role == Role.ADMIN
    assert persisted.google_id is None  # pre-alta, sin vincular


async def test_bootstrap_idempotente_segunda_vez_no_hace_nada(
    db: AsyncSession,
) -> None:
    repo = SqlUserRepository(db)
    bootstrap = BootstrapInitialAdmin(repo)

    a = await bootstrap("admin@x.com")
    assert a is not None
    b = await bootstrap("admin@x.com")  # repetir
    assert b is None  # no hizo nada

    all_users = await repo.list_all()
    assert len(all_users) == 1


# ─────────────────── register_user (use case + repo real) ───────────────────


async def test_register_user_persiste_pre_alta(db: AsyncSession) -> None:
    repo = SqlUserRepository(db)
    bootstrap = BootstrapInitialAdmin(repo)
    admin = await bootstrap("admin@x.com")
    assert admin is not None

    use_case = RegisterUser(repo)
    new = await use_case(actor=admin, email="invited@x.com", role=Role.ANALYST)

    persisted = await repo.find_by_email("invited@x.com")
    assert persisted is not None
    assert persisted.id == new.id
    assert persisted.role == Role.ANALYST
    assert persisted.google_id is None
