"""E2E adicionales para los handlers de error de los endpoints que no
estaban cubiertos por los tests del camino feliz.

Pruebas dirigidas a:
- `/api/v1/weeks/*` y `/screening/matrix`: cuando la ACL lanza
  `AnalysisSchemaMismatchError` → 500 `analysis_schema_mismatch`.
- `/api/v1/backtests`:
  - `?status=invalid` → 400 `bad_request`.
  - cancel/snapshot/result con id inexistente → 404.
"""
import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.domain.access.google_identity import GoogleIdentity
from app.domain.access.role import Role
from app.domain.access.user import User
from app.infrastructure.analysis_acl.exceptions import AnalysisSchemaMismatchError
from app.infrastructure.persistence.app_db import SessionFactory
from app.infrastructure.repositories.user_repository import SqlUserRepository
from app.infrastructure.web.dependencies import get_google_verifier
from app.infrastructure.web.v1.screening import get_screening_reader
from app.main import create_app

from tests.unit.application.fakes.fake_google_verifier import FakeGoogleIdentityVerifier


class BrokenScreeningReader:
    """Reader que lanza `AnalysisSchemaMismatchError` en cualquier método."""

    async def list_runs_in_period(self, **_):  # type: ignore[no-untyped-def]
        raise AnalysisSchemaMismatchError(missing=["analysis_runs.status"])

    async def get_picks_for_run(self, **_):  # type: ignore[no-untyped-def]
        raise AnalysisSchemaMismatchError(missing=["analysis_runs.status"])

    async def get_company_data(self, **_):  # type: ignore[no-untyped-def]
        raise AnalysisSchemaMismatchError(missing=["analysis_runs.status"])

    async def list_universe_for_run(self, **_):  # type: ignore[no-untyped-def]
        raise AnalysisSchemaMismatchError(missing=["analysis_runs.status"])

    async def get_companies_metadata(self, **_):  # type: ignore[no-untyped-def]
        raise AnalysisSchemaMismatchError(missing=["analysis_runs.status"])

    async def list_companies_summary_for_run(self, **_):  # type: ignore[no-untyped-def]
        raise AnalysisSchemaMismatchError(missing=["analysis_runs.status"])


@pytest.fixture(autouse=True)
async def _wipe() -> None:
    async with SessionFactory() as s:
        for t in (
            "backtest_snapshot_pick", "backtest_snapshot_week",
            "backtest_equity_point", "backtest_result", "backtest", "app_user",
        ):
            await s.execute(text(f"DELETE FROM {t}"))
        await s.commit()


@pytest.fixture
async def client_broken_acl() -> AsyncIterator[AsyncClient]:
    """Cliente con la ACL del análisis siempre rompiendo (schema mismatch)."""
    app = create_app(skip_bootstrap=True)
    fake_google = FakeGoogleIdentityVerifier()
    app.dependency_overrides[get_google_verifier] = lambda: fake_google
    app.dependency_overrides[get_screening_reader] = lambda: BrokenScreeningReader()

    async with SessionFactory() as s:
        await SqlUserRepository(s).save(
            User(id=uuid.uuid4(), email="a@x.com", role=Role.ANALYST, google_id=None),
        )
    fake_google.set_identity(
        "tok", GoogleIdentity(google_id="ga", email="a@x.com")
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        # login para obtener bearer
        r = await c.post("/api/v1/auth/google", json={"id_token": "tok"})
        token = r.json()["access_token"]
        c.headers["Authorization"] = f"Bearer {token}"
        yield c


@pytest.fixture
async def client_normal() -> AsyncIterator[AsyncClient]:
    """Cliente con dependencias normales pero usuario analyst pre-cargado."""
    app = create_app(skip_bootstrap=True)
    fake_google = FakeGoogleIdentityVerifier()
    app.dependency_overrides[get_google_verifier] = lambda: fake_google

    async with SessionFactory() as s:
        await SqlUserRepository(s).save(
            User(id=uuid.uuid4(), email="a@x.com", role=Role.ANALYST, google_id=None),
        )
    fake_google.set_identity(
        "tok", GoogleIdentity(google_id="ga", email="a@x.com")
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        r = await c.post("/api/v1/auth/google", json={"id_token": "tok"})
        token = r.json()["access_token"]
        c.headers["Authorization"] = f"Bearer {token}"
        yield c


# ────────────── Screening: AnalysisSchemaMismatchError → 500 ──────────────


async def test_weeks_schema_mismatch_devuelve_500(
    client_broken_acl: AsyncClient,
) -> None:
    r = await client_broken_acl.get("/api/v1/weeks")
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "analysis_schema_mismatch"


async def test_picks_schema_mismatch_devuelve_500(
    client_broken_acl: AsyncClient,
) -> None:
    r = await client_broken_acl.get("/api/v1/weeks/2026-01-05/picks")
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "analysis_schema_mismatch"


async def test_companies_schema_mismatch_devuelve_500(
    client_broken_acl: AsyncClient,
) -> None:
    r = await client_broken_acl.get("/api/v1/weeks/2026-01-05/companies")
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "analysis_schema_mismatch"


async def test_company_detail_schema_mismatch_devuelve_500(
    client_broken_acl: AsyncClient,
) -> None:
    r = await client_broken_acl.get("/api/v1/weeks/2026-01-05/companies/AAPL")
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "analysis_schema_mismatch"


async def test_matrix_schema_mismatch_devuelve_500(
    client_broken_acl: AsyncClient,
) -> None:
    r = await client_broken_acl.get(
        "/api/v1/screening/matrix?from=2026-01-05&to=2026-01-12"
    )
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "analysis_schema_mismatch"


# ────────────── Backtests: paths sin cubrir ──────────────


async def test_list_backtests_status_invalido_devuelve_400(
    client_normal: AsyncClient,
) -> None:
    r = await client_normal.get("/api/v1/backtests?status=invalid_status_value")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "bad_request"


async def test_cancel_backtest_id_inexistente_devuelve_404(
    client_normal: AsyncClient,
) -> None:
    r = await client_normal.post(f"/api/v1/backtests/{uuid.uuid4()}/cancel")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "backtest_not_found"


async def test_get_snapshot_id_inexistente_devuelve_404(
    client_normal: AsyncClient,
) -> None:
    r = await client_normal.get(f"/api/v1/backtests/{uuid.uuid4()}/snapshot")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "backtest_not_found"
