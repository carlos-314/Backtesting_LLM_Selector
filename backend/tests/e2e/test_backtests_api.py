"""E2E de `/api/v1/backtests/*` (F2 §6.5, §8.4)."""
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.domain.access.google_identity import GoogleIdentity
from app.domain.access.role import Role
from app.domain.access.user import User
from app.domain.backtesting.parameters import BacktestId
from app.infrastructure.persistence.app_db import SessionFactory
from app.infrastructure.repositories.user_repository import SqlUserRepository
from app.infrastructure.web.dependencies import get_google_verifier
from app.infrastructure.web.v1.backtests import get_job_enqueuer
from app.main import create_app

from tests.unit.application.fakes.fake_google_verifier import FakeGoogleIdentityVerifier


@dataclass
class FakeJobEnqueuer:
    enqueued: list[BacktestId] = field(default_factory=list)

    async def enqueue_run_backtest(self, backtest_id: BacktestId) -> None:
        self.enqueued.append(backtest_id)


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
async def fake_google() -> FakeGoogleIdentityVerifier:
    return FakeGoogleIdentityVerifier()


@pytest.fixture
async def fake_enqueuer() -> FakeJobEnqueuer:
    return FakeJobEnqueuer()


@pytest.fixture
async def client(
    fake_google: FakeGoogleIdentityVerifier,
    fake_enqueuer: FakeJobEnqueuer,
) -> AsyncIterator[AsyncClient]:
    app = create_app(skip_bootstrap=True)
    app.dependency_overrides[get_google_verifier] = lambda: fake_google
    app.dependency_overrides[get_job_enqueuer] = lambda: fake_enqueuer
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


async def _seed_user(*, email: str, role: Role) -> User:
    async with SessionFactory() as s:
        u = User(id=uuid.uuid4(), email=email, role=role, google_id=None)
        await SqlUserRepository(s).save(u)
        return u


async def _login(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier, email: str
) -> str:
    fake_google.set_identity("tok_" + email, GoogleIdentity(google_id="g_" + email, email=email))
    r = await client.post("/api/v1/auth/google", json={"id_token": "tok_" + email})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


# ════════════════════════ POST /backtests ════════════════════════


async def test_analyst_crea_backtest_devuelve_202_y_encola(
    client: AsyncClient,
    fake_google: FakeGoogleIdentityVerifier,
    fake_enqueuer: FakeJobEnqueuer,
) -> None:
    await _seed_user(email="a@x.com", role=Role.ANALYST)
    token = await _login(client, fake_google, "a@x.com")

    r = await client.post(
        "/api/v1/backtests",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "BT1",
            "period_start": "2026-01-05",
            "period_end": "2026-01-26",
            "initial_capital": "10000",
        },
    )
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "pending"
    assert body["name"] == "BT1"
    assert body["period"] == {"start": "2026-01-05", "end": "2026-01-26"}

    # Encolado
    assert len(fake_enqueuer.enqueued) == 1
    assert str(fake_enqueuer.enqueued[0]) == body["id"]


async def test_viewer_no_puede_crear_backtest_devuelve_403(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier
) -> None:
    await _seed_user(email="v@x.com", role=Role.VIEWER)
    token = await _login(client, fake_google, "v@x.com")
    r = await client.post(
        "/api/v1/backtests",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "BT"},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "backtest_not_permitted"


async def test_crear_backtest_periodo_invertido_devuelve_422(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier
) -> None:
    await _seed_user(email="a@x.com", role=Role.ANALYST)
    token = await _login(client, fake_google, "a@x.com")
    r = await client.post(
        "/api/v1/backtests",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "BT", "period_start": "2026-02-02", "period_end": "2026-01-05",
        },
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_period"


async def test_crear_backtest_capital_negativo_devuelve_422(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier
) -> None:
    await _seed_user(email="a@x.com", role=Role.ANALYST)
    token = await _login(client, fake_google, "a@x.com")
    r = await client.post(
        "/api/v1/backtests",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "BT", "initial_capital": "-1"},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_capital"


async def test_crear_backtest_sin_sesion_devuelve_401(client: AsyncClient) -> None:
    r = await client.post("/api/v1/backtests", json={"name": "BT"})
    assert r.status_code == 401


# ════════════════════════ GET /backtests ════════════════════════


async def test_list_backtests_devuelve_lista_ordenada_desc_por_creacion(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier
) -> None:
    await _seed_user(email="a@x.com", role=Role.ANALYST)
    token = await _login(client, fake_google, "a@x.com")
    headers = {"Authorization": f"Bearer {token}"}

    for i in range(3):
        r = await client.post(
            "/api/v1/backtests", headers=headers,
            json={"name": f"BT{i}", "period_start": "2026-01-05", "period_end": "2026-01-12"},
        )
        assert r.status_code == 202

    r = await client.get("/api/v1/backtests", headers=headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 3
    # Más reciente primero
    names = [it["name"] for it in items]
    assert names == ["BT2", "BT1", "BT0"]


async def test_list_backtests_filtra_por_status(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier
) -> None:
    await _seed_user(email="a@x.com", role=Role.ANALYST)
    token = await _login(client, fake_google, "a@x.com")
    headers = {"Authorization": f"Bearer {token}"}

    # 2 pending + 1 cancelled
    ids = []
    for i in range(3):
        r = await client.post(
            "/api/v1/backtests", headers=headers,
            json={"name": f"BT{i}", "period_start": "2026-01-05", "period_end": "2026-01-12"},
        )
        ids.append(r.json()["id"])

    # Cancelar uno
    await client.post(f"/api/v1/backtests/{ids[0]}/cancel", headers=headers)

    r = await client.get("/api/v1/backtests?status=pending", headers=headers)
    assert {it["name"] for it in r.json()["items"]} == {"BT1", "BT2"}

    r = await client.get("/api/v1/backtests?status=cancelled", headers=headers)
    assert {it["name"] for it in r.json()["items"]} == {"BT0"}


# ════════════════════════ GET /backtests/{id} ════════════════════════


async def test_get_backtest_id_no_encontrado_devuelve_404(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier
) -> None:
    await _seed_user(email="a@x.com", role=Role.ANALYST)
    token = await _login(client, fake_google, "a@x.com")
    r = await client.get(
        f"/api/v1/backtests/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "backtest_not_found"


async def test_get_backtest_devuelve_estado(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier
) -> None:
    await _seed_user(email="a@x.com", role=Role.ANALYST)
    token = await _login(client, fake_google, "a@x.com")
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post(
        "/api/v1/backtests", headers=headers,
        json={"name": "BT", "period_start": "2026-01-05", "period_end": "2026-01-12"},
    )
    bt_id = r.json()["id"]

    r2 = await client.get(f"/api/v1/backtests/{bt_id}", headers=headers)
    assert r2.status_code == 200
    assert r2.json()["status"] == "pending"


# ════════════════════ POST /backtests/{id}/cancel ════════════════════


async def test_cancel_backtest_pending_devuelve_202_cancelled(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier
) -> None:
    await _seed_user(email="a@x.com", role=Role.ANALYST)
    token = await _login(client, fake_google, "a@x.com")
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post(
        "/api/v1/backtests", headers=headers,
        json={"name": "BT", "period_start": "2026-01-05", "period_end": "2026-01-12"},
    )
    bt_id = r.json()["id"]

    r2 = await client.post(f"/api/v1/backtests/{bt_id}/cancel", headers=headers)
    assert r2.status_code == 202
    assert r2.json()["status"] == "cancelled"


async def test_cancel_backtest_ya_cancelled_devuelve_409(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier
) -> None:
    await _seed_user(email="a@x.com", role=Role.ANALYST)
    token = await _login(client, fake_google, "a@x.com")
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post(
        "/api/v1/backtests", headers=headers,
        json={"name": "BT", "period_start": "2026-01-05", "period_end": "2026-01-12"},
    )
    bt_id = r.json()["id"]
    await client.post(f"/api/v1/backtests/{bt_id}/cancel", headers=headers)
    r3 = await client.post(f"/api/v1/backtests/{bt_id}/cancel", headers=headers)
    assert r3.status_code == 409
    assert r3.json()["error"]["code"] == "not_cancellable"


async def test_viewer_no_puede_cancelar_backtest_devuelve_403(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier
) -> None:
    # Analyst crea
    await _seed_user(email="a@x.com", role=Role.ANALYST)
    analyst_token = await _login(client, fake_google, "a@x.com")
    r = await client.post(
        "/api/v1/backtests",
        headers={"Authorization": f"Bearer {analyst_token}"},
        json={"name": "BT", "period_start": "2026-01-05", "period_end": "2026-01-12"},
    )
    bt_id = r.json()["id"]

    # Viewer intenta cancelar
    await _seed_user(email="v@x.com", role=Role.VIEWER)
    viewer_token = await _login(client, fake_google, "v@x.com")
    r2 = await client.post(
        f"/api/v1/backtests/{bt_id}/cancel",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert r2.status_code == 403


# ════════════════════ GET /backtests/{id}/result ════════════════════


async def test_get_result_de_un_pending_devuelve_409(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier
) -> None:
    """F2 §6.5: 409 backtest_not_ready distingue 'no existe' de 'aún procesa'."""
    await _seed_user(email="a@x.com", role=Role.ANALYST)
    token = await _login(client, fake_google, "a@x.com")
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post(
        "/api/v1/backtests", headers=headers,
        json={"name": "BT", "period_start": "2026-01-05", "period_end": "2026-01-12"},
    )
    bt_id = r.json()["id"]
    r2 = await client.get(f"/api/v1/backtests/{bt_id}/result", headers=headers)
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "backtest_not_ready"


async def test_get_snapshot_de_un_pending_devuelve_409(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier
) -> None:
    await _seed_user(email="a@x.com", role=Role.ANALYST)
    token = await _login(client, fake_google, "a@x.com")
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post(
        "/api/v1/backtests", headers=headers,
        json={"name": "BT", "period_start": "2026-01-05", "period_end": "2026-01-12"},
    )
    bt_id = r.json()["id"]
    r2 = await client.get(f"/api/v1/backtests/{bt_id}/snapshot", headers=headers)
    assert r2.status_code == 409


async def test_get_result_id_inexistente_devuelve_404(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier
) -> None:
    await _seed_user(email="a@x.com", role=Role.ANALYST)
    token = await _login(client, fake_google, "a@x.com")
    r = await client.get(
        f"/api/v1/backtests/{uuid.uuid4()}/result",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404
