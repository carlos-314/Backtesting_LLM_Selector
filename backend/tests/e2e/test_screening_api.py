"""E2E de `/api/v1/weeks/*` y `/api/v1/screening/matrix` (F2 §6.4, §8.4)."""
import uuid
from collections.abc import AsyncIterator
from datetime import date, datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domain.access.google_identity import GoogleIdentity
from app.domain.access.role import Role
from app.domain.access.user import User
from app.domain.shared.week import NEW_YORK
from app.infrastructure.persistence.app_db import SessionFactory
from app.infrastructure.repositories.user_repository import SqlUserRepository
from app.infrastructure.web.dependencies import get_google_verifier
from app.main import create_app

from tests.unit.application.fakes.fake_google_verifier import FakeGoogleIdentityVerifier


ANALYSIS_TEST_URL = (
    "postgresql+asyncpg://backtesting:backtesting_dev@localhost:55432/backtesting_analysis_test"
)


# ────────────────────── fixtures ──────────────────────


@pytest.fixture(autouse=True)
async def _wipe_app_db() -> None:
    async with SessionFactory() as s:
        for t in (
            "backtest_snapshot_pick", "backtest_snapshot_week",
            "backtest_equity_point", "backtest_result", "backtest", "app_user",
        ):
            await s.execute(text(f"DELETE FROM {t}"))
        await s.commit()


@pytest.fixture(autouse=True)
async def _setup_analysis() -> AsyncIterator[None]:
    """Crea el schema legacy en backtesting_analysis_test (analysis_runs,
    portfolios + processed_stocks + stock) y lo pobla con datos curados."""
    engine = create_async_engine(ANALYSIS_TEST_URL, echo=False)
    SessionMaker = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        for stmt in (
            "DROP TABLE IF EXISTS portfolios",
            "DROP TABLE IF EXISTS processed_stocks",
            "DROP TABLE IF EXISTS analysis_runs",
            "DROP TABLE IF EXISTS stock",
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
            """
            CREATE TABLE processed_stocks (
                id_processed_stock serial PRIMARY KEY,
                id_run             integer,
                "Ticker"           character varying(20),
                "Nom"              character varying(255),
                "Country"          character varying(100),
                "Exchange"         character varying(100),
                "StockCurrency"    character varying(10),
                "CAGRPOT"          numeric
            )
            """,
            """
            CREATE TABLE stock (
                ticker          text PRIMARY KEY,
                nombre          text,
                exchange        text,
                pais            text,
                currency        text
            )
            """,
        ):
            await conn.execute(text(stmt))

    async with SessionMaker() as s:
        # Dos semanas con dos picks cada una; tres empresas en universo.
        await s.execute(text("""
            INSERT INTO analysis_runs (id_run, "fechaRun", run_code, status) VALUES
                (1, :d1, 'R1', 'COMPLETED'),
                (2, :d2, 'R2', 'COMPLETED')
        """), {
            "d1": datetime(2026, 1, 5, 9, 0, tzinfo=NEW_YORK),
            "d2": datetime(2026, 1, 12, 9, 0, tzinfo=NEW_YORK),
        })
        await s.execute(text("""
            INSERT INTO portfolios (id_portfolio, id_run, ticker, rol) VALUES
                (1, 1, 'AAPL', 'core'),
                (2, 1, 'MSFT', 'core'),
                (3, 2, 'AAPL', 'core'),
                (4, 2, 'NVDA', 'core')
        """))
        await s.execute(text("""
            INSERT INTO processed_stocks (id_run, "Ticker", "Nom", "Country", "Exchange", "StockCurrency", "CAGRPOT") VALUES
                (1, 'AAPL', 'Apple Inc.', 'US', 'NASDAQ', 'USD', 0.12),
                (1, 'MSFT', 'Microsoft', 'US', 'NASDAQ', 'USD', 0.10),
                (1, 'GOOG', 'Alphabet',  'US', 'NASDAQ', 'USD', 0.08),
                (2, 'AAPL', 'Apple Inc.', 'US', 'NASDAQ', 'USD', 0.13),
                (2, 'NVDA', 'NVIDIA',     'US', 'NASDAQ', 'USD', 0.25),
                (2, 'TSLA', 'Tesla',      'US', 'NASDAQ', 'USD', 0.05)
        """))
        await s.execute(text("""
            INSERT INTO stock (ticker, nombre, exchange, pais, currency) VALUES
                ('AAPL', 'Apple Inc.', 'NASDAQ', 'US', 'USD'),
                ('MSFT', 'Microsoft', 'NASDAQ', 'US', 'USD'),
                ('GOOG', 'Alphabet',  'NASDAQ', 'US', 'USD'),
                ('NVDA', 'NVIDIA',    'NASDAQ', 'US', 'USD'),
                ('TSLA', 'Tesla',     'NASDAQ', 'US', 'USD')
        """))
        await s.commit()

    yield
    await engine.dispose()


@pytest.fixture
def _redirect_analysis_session(monkeypatch):
    """Apunta la SessionFactory de análisis al BBDD test."""
    test_engine = create_async_engine(ANALYSIS_TEST_URL, echo=False)
    test_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    monkeypatch.setattr(
        "app.infrastructure.web.dependencies.AnalysisSessionFactory",
        test_factory,
    )


@pytest.fixture
async def fake_google() -> FakeGoogleIdentityVerifier:
    return FakeGoogleIdentityVerifier()


@pytest.fixture
async def client(
    _redirect_analysis_session, fake_google: FakeGoogleIdentityVerifier
) -> AsyncIterator[AsyncClient]:
    app = create_app(skip_bootstrap=True)
    app.dependency_overrides[get_google_verifier] = lambda: fake_google
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


async def _login_admin(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier
) -> str:
    """Seed admin + login. Devuelve el bearer."""
    async with SessionFactory() as s:
        repo = SqlUserRepository(s)
        await repo.save(User(
            id=uuid.uuid4(), email="a@x.com", role=Role.ADMIN, google_id=None,
        ))
    fake_google.set_identity("tok", GoogleIdentity(google_id="g_a", email="a@x.com"))
    r = await client.post("/api/v1/auth/google", json={"id_token": "tok"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


# ════════════════════════ /weeks ════════════════════════


async def test_get_weeks_devuelve_dos_semanas_ordenadas_descendente(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier
) -> None:
    token = await _login_admin(client, fake_google)
    r = await client.get(
        "/api/v1/weeks?from=2026-01-05&to=2026-01-12",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) == 2
    assert items[0]["week_date"] == "2026-01-12"  # más reciente primero
    assert items[1]["week_date"] == "2026-01-05"
    assert items[0]["pick_count"] == 2


async def test_get_weeks_sin_sesion_devuelve_401(client: AsyncClient) -> None:
    r = await client.get("/api/v1/weeks")
    assert r.status_code == 401


# ═════════════════ /weeks/{w}/picks ═════════════════


async def test_get_picks_devuelve_picks_de_la_semana(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier
) -> None:
    token = await _login_admin(client, fake_google)
    r = await client.get(
        "/api/v1/weeks/2026-01-12/picks",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert {p["ticker"] for p in items} == {"AAPL", "NVDA"}


async def test_get_picks_semana_no_resuelta_devuelve_404(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier
) -> None:
    token = await _login_admin(client, fake_google)
    r = await client.get(
        "/api/v1/weeks/2026-02-02/picks",  # no hay run esa semana
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "week_not_found"


# ═════════════════ /weeks/{w}/companies ═════════════════


async def test_list_companies_devuelve_universo_paginado(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier
) -> None:
    token = await _login_admin(client, fake_google)
    r = await client.get(
        "/api/v1/weeks/2026-01-05/companies?limit=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 2  # primeras 2 de 3
    assert body["next_cursor"] is not None

    # Página siguiente
    r2 = await client.get(
        f"/api/v1/weeks/2026-01-05/companies?limit=2&cursor={body['next_cursor']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200
    body2 = r2.json()
    assert len(body2["items"]) == 1  # 1 restante
    assert body2["next_cursor"] is None  # no hay más


async def test_list_companies_marca_in_portfolio_correctamente(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier
) -> None:
    token = await _login_admin(client, fake_google)
    r = await client.get(
        "/api/v1/weeks/2026-01-05/companies",
        headers={"Authorization": f"Bearer {token}"},
    )
    items = r.json()["items"]
    by_ticker = {it["ticker"]: it["in_portfolio"] for it in items}
    assert by_ticker == {"AAPL": True, "MSFT": True, "GOOG": False}


# ═════════════ /weeks/{w}/companies/{ticker} (ficha) ═════════════


async def test_get_company_existente_devuelve_ficha(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier
) -> None:
    token = await _login_admin(client, fake_google)
    r = await client.get(
        "/api/v1/weeks/2026-01-05/companies/AAPL",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ticker"] == "AAPL"
    assert body["name"] == "Apple Inc."
    assert body["in_portfolio"] is True
    # ADR-0002 pendiente: shape mínimo + raw
    assert "raw_processed_stock" in body


async def test_get_company_no_existente_en_run_devuelve_404(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier
) -> None:
    token = await _login_admin(client, fake_google)
    r = await client.get(
        "/api/v1/weeks/2026-01-05/companies/UNKNOWN",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "company_not_found"


# ═════════════════════ /screening/matrix ═════════════════════


async def test_get_matrix_estructura_correcta(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier
) -> None:
    """ADR-0001: ejes resueltos + celdas dispersas."""
    token = await _login_admin(client, fake_google)
    r = await client.get(
        "/api/v1/screening/matrix?from=2026-01-05&to=2026-01-12",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert {"weeks", "companies", "cells"} == set(body.keys())

    # 2 semanas
    week_dates = {w["week_date"] for w in body["weeks"]}
    assert week_dates == {"2026-01-05", "2026-01-12"}

    # 5 empresas únicas en universo (AAPL, MSFT, GOOG, NVDA, TSLA)
    tickers = {c["ticker"] for c in body["companies"]}
    assert tickers == {"AAPL", "MSFT", "GOOG", "NVDA", "TSLA"}

    # Cells: AAPL @ 5/Ene selected, AAPL @ 12/Ene selected, GOOG in_universe...
    cells_by_key = {(c["ticker"], c["week_date"]): c["state"] for c in body["cells"]}
    assert cells_by_key[("AAPL", "2026-01-05")] == "selected"
    assert cells_by_key[("AAPL", "2026-01-12")] == "selected"
    assert cells_by_key[("MSFT", "2026-01-05")] == "selected"
    assert cells_by_key[("GOOG", "2026-01-05")] == "in_universe"
    # GOOG no aparece en run 2 (no estuvo en universo):
    assert ("GOOG", "2026-01-12") not in cells_by_key


async def test_get_matrix_rango_demasiado_amplio_devuelve_422(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier
) -> None:
    token = await _login_admin(client, fake_google)
    r = await client.get(
        "/api/v1/screening/matrix?from=2020-01-06&to=2026-01-05",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "range_too_wide"


async def test_get_matrix_from_mayor_que_to_devuelve_400(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier
) -> None:
    token = await _login_admin(client, fake_google)
    r = await client.get(
        "/api/v1/screening/matrix?from=2026-01-12&to=2026-01-05",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400


async def test_get_matrix_sin_sesion_devuelve_401(client: AsyncClient) -> None:
    r = await client.get("/api/v1/screening/matrix?from=2026-01-05&to=2026-01-12")
    assert r.status_code == 401
