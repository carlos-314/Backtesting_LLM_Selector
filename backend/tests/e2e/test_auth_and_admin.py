"""E2E de `/api/v1/auth/*` y `/api/v1/admin/users` (F2 §6.3, §8.4, ADR-0006/0007).

Google se mockea (F2 §8.5). Postgres real. Suite e2e.
"""
import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.domain.access.google_identity import GoogleIdentity
from app.domain.access.role import Role
from app.domain.access.user import User
from app.infrastructure.persistence.app_db import SessionFactory
from app.infrastructure.repositories.user_repository import SqlUserRepository
from app.infrastructure.web.dependencies import get_google_verifier
from app.main import create_app

from tests.unit.application.fakes.fake_google_verifier import FakeGoogleIdentityVerifier


# ────────────────────── fixtures ──────────────────────


@pytest.fixture(autouse=True)
async def _wipe() -> None:
    async with SessionFactory() as s:
        for t in (
            "backtest_snapshot_pick", "backtest_snapshot_week",
            "backtest_equity_point", "backtest_result", "backtest",
            "app_user",
        ):
            await s.execute(text(f"DELETE FROM {t}"))
        await s.commit()


@pytest.fixture
async def fake_google() -> FakeGoogleIdentityVerifier:
    return FakeGoogleIdentityVerifier()


@pytest.fixture
async def client(fake_google: FakeGoogleIdentityVerifier) -> AsyncIterator[AsyncClient]:
    app = create_app(skip_bootstrap=True)
    app.dependency_overrides[get_google_verifier] = lambda: fake_google
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


async def _seed_admin(email: str = "admin@x.com", google_id: str | None = None) -> User:
    async with SessionFactory() as s:
        repo = SqlUserRepository(s)
        admin = User(
            id=uuid.uuid4(), email=email, role=Role.ADMIN,
            is_active=True, full_name="Admin", google_id=google_id,
        )
        await repo.save(admin)
        return admin


async def _seed_user(
    *, email: str, role: Role, google_id: str | None = None, is_active: bool = True
) -> User:
    async with SessionFactory() as s:
        repo = SqlUserRepository(s)
        u = User(
            id=uuid.uuid4(), email=email, role=role,
            is_active=is_active, google_id=google_id,
        )
        await repo.save(u)
        return u


# ════════════════════════ POST /auth/google ════════════════════════


async def test_login_con_admin_pre_aprobado_vincula_y_devuelve_tokens(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier
) -> None:
    """ADR-0006: pre-alta con google_id=NULL; primer login vincula."""
    admin = await _seed_admin(email="admin@x.com", google_id=None)
    fake_google.set_identity(
        "tok1", GoogleIdentity(google_id="g_admin", email="admin@x.com", full_name="Admin")
    )

    r = await client.post("/api/v1/auth/google", json={"id_token": "tok1"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    assert body["user"]["email"] == "admin@x.com"
    assert body["user"]["role"] == "admin"


async def test_login_con_email_no_autorizado_devuelve_403(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier
) -> None:
    fake_google.set_identity(
        "tok", GoogleIdentity(google_id="gX", email="random@x.com")
    )
    r = await client.post("/api/v1/auth/google", json={"id_token": "tok"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "user_not_authorized"


async def test_login_con_id_token_invalido_devuelve_401(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier
) -> None:
    # No seteamos ninguna identidad → el fake lanza InvalidGoogleTokenError
    r = await client.post("/api/v1/auth/google", json={"id_token": "bogus"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_google_token"


async def test_login_con_google_caido_devuelve_502(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier
) -> None:
    fake_google.fail_unreachable = True
    r = await client.post("/api/v1/auth/google", json={"id_token": "anything"})
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "google_unreachable"


async def test_login_body_sin_id_token_devuelve_400(client: AsyncClient) -> None:
    r = await client.post("/api/v1/auth/google", json={})
    assert r.status_code == 400


# ════════════════════════ GET /auth/me ════════════════════════


async def _login_as(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier, *, email: str, google_id: str
) -> str:
    fake_google.set_identity(google_id, GoogleIdentity(google_id=google_id, email=email))
    r = await client.post("/api/v1/auth/google", json={"id_token": google_id})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def test_me_sin_authorization_header_devuelve_401(client: AsyncClient) -> None:
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


async def test_me_con_bearer_invalido_devuelve_401(client: AsyncClient) -> None:
    r = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not.a.real.jwt"},
    )
    assert r.status_code == 401


async def test_me_con_token_valido_devuelve_user(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier
) -> None:
    await _seed_admin(email="me@x.com", google_id=None)
    token = await _login_as(client, fake_google, email="me@x.com", google_id="g_me")

    r = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "me@x.com"
    assert body["role"] == "admin"


# ════════════════════════ POST /auth/logout ════════════════════════


async def test_logout_con_token_valido_devuelve_204(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier
) -> None:
    await _seed_admin(email="me@x.com")
    token = await _login_as(client, fake_google, email="me@x.com", google_id="g_me")
    r = await client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 204


async def test_logout_sin_bearer_devuelve_401(client: AsyncClient) -> None:
    r = await client.post("/api/v1/auth/logout")
    assert r.status_code == 401


# ════════════════════════ POST /admin/users ════════════════════════


async def test_admin_crea_usuario_pre_aprobado(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier
) -> None:
    await _seed_admin(email="admin@x.com")
    token = await _login_as(client, fake_google, email="admin@x.com", google_id="g_admin")

    r = await client.post(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "invited@x.com", "role": "analyst"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["email"] == "invited@x.com"
    assert body["role"] == "analyst"
    assert body["is_active"] is True


async def test_admin_crea_usuario_email_duplicado_devuelve_409(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier
) -> None:
    await _seed_admin(email="admin@x.com")
    await _seed_user(email="dup@x.com", role=Role.VIEWER)
    token = await _login_as(client, fake_google, email="admin@x.com", google_id="g_admin")

    r = await client.post(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "dup@x.com", "role": "analyst"},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "email_already_registered"


async def test_admin_crea_usuario_email_invalido_devuelve_400(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier
) -> None:
    await _seed_admin(email="admin@x.com")
    token = await _login_as(client, fake_google, email="admin@x.com", google_id="g_admin")

    r = await client.post(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "not_an_email", "role": "analyst"},
    )
    assert r.status_code == 400  # validation error de Pydantic via handler


async def test_admin_crea_usuario_role_invalido_devuelve_400(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier
) -> None:
    await _seed_admin(email="admin@x.com")
    token = await _login_as(client, fake_google, email="admin@x.com", google_id="g_admin")

    r = await client.post(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "x@x.com", "role": "superuser"},
    )
    assert r.status_code == 400


async def test_analyst_no_puede_crear_usuario_devuelve_403(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier
) -> None:
    """F1 §5 / ADR-0006: solo admin gestiona usuarios."""
    await _seed_user(email="analyst@x.com", role=Role.ANALYST)
    token = await _login_as(client, fake_google, email="analyst@x.com", google_id="g_a")

    r = await client.post(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "new@x.com", "role": "viewer"},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


async def test_viewer_no_puede_crear_usuario_devuelve_403(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier
) -> None:
    await _seed_user(email="viewer@x.com", role=Role.VIEWER)
    token = await _login_as(client, fake_google, email="viewer@x.com", google_id="g_v")

    r = await client.post(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "new@x.com", "role": "viewer"},
    )
    assert r.status_code == 403


async def test_sin_bearer_no_puede_crear_usuario_devuelve_401(
    client: AsyncClient,
) -> None:
    r = await client.post(
        "/api/v1/admin/users",
        json={"email": "new@x.com", "role": "viewer"},
    )
    assert r.status_code == 401


# ════════════════════════ GET /admin/users ════════════════════════


async def test_admin_lista_usuarios(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier
) -> None:
    await _seed_admin(email="admin@x.com")
    await _seed_user(email="b@x.com", role=Role.VIEWER)
    await _seed_user(email="c@x.com", role=Role.ANALYST)
    token = await _login_as(client, fake_google, email="admin@x.com", google_id="g_admin")

    r = await client.get(
        "/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    items = r.json()["items"]
    emails = {u["email"] for u in items}
    assert {"admin@x.com", "b@x.com", "c@x.com"} <= emails


async def test_no_admin_no_lista_usuarios_devuelve_403(
    client: AsyncClient, fake_google: FakeGoogleIdentityVerifier
) -> None:
    await _seed_user(email="a@x.com", role=Role.ANALYST)
    token = await _login_as(client, fake_google, email="a@x.com", google_id="ga")
    r = await client.get(
        "/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 403
