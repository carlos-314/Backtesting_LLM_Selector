"""E2E del andamiaje (pieza 1).

Cubre F2 §6.2 (health), §6.1 (shape uniforme, request_id), §7.1 (correlación).

Estos tests asumen:
- Postgres local levantado (`docker compose up -d postgres`) → BBDD APP.
- ANALYSIS_DATABASE_URL en .env apunta a Railway con user read-only.

Si la BBDD de análisis no es alcanzable (red caída), el test que la pide OK
se marcará como degraded — es comportamiento correcto, no fallo del test.
"""
import re

import pytest
from httpx import AsyncClient

from app.infrastructure.web.logging import HEADER as REQUEST_ID_HEADER


# ─────────────────────────── /health ───────────────────────────


async def test_health_responde_con_shape_esperado(http_client: AsyncClient) -> None:
    r = await http_client.get("/api/v1/health")
    assert r.status_code in (200, 503), r.text
    body = r.json()
    assert set(body.keys()) == {"status", "checks"}
    assert body["status"] in ("ok", "degraded")
    assert set(body["checks"].keys()) == {"db_app", "db_analysis"}
    assert body["checks"]["db_app"] in ("ok", "degraded")
    assert body["checks"]["db_analysis"] in ("ok", "degraded")


async def test_health_db_app_local_responde_ok(http_client: AsyncClient) -> None:
    """La BBDD propia local (docker compose) debe estar OK durante los tests."""
    r = await http_client.get("/api/v1/health")
    body = r.json()
    assert body["checks"]["db_app"] == "ok", (
        "BBDD propia local no responde. "
        "Levanta con: docker compose up -d postgres"
    )


async def test_health_devuelve_503_cuando_overall_no_ok(
    http_client: AsyncClient, monkeypatch
) -> None:
    """Si alguno de los chequeos está degradado, el endpoint devuelve 503."""
    # Forzamos un fallo en el ping de db_app sustituyendo la función _ping.
    from app.infrastructure.web.v1 import health as health_mod

    async def fake_ping(*_args, **_kwargs):
        return "degraded"

    monkeypatch.setattr(health_mod, "_ping", fake_ping)

    r = await http_client.get("/api/v1/health")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "degraded"
    assert body["checks"]["db_app"] == "degraded"
    assert body["checks"]["db_analysis"] == "degraded"


# ─────────────────────── Shape uniforme de error ───────────────────────


async def test_404_devuelve_shape_uniforme(http_client: AsyncClient) -> None:
    r = await http_client.get("/api/v1/ruta-inexistente")
    assert r.status_code == 404
    body = r.json()
    assert "error" in body
    assert body["error"]["code"] == "not_found"
    assert isinstance(body["error"]["message"], str)
    assert "details" in body["error"]


# ─────────────────── Middleware de request_id (F2 §7.1) ───────────────────


async def test_request_id_se_genera_si_no_viene(http_client: AsyncClient) -> None:
    r = await http_client.get("/api/v1/health")
    rid = r.headers.get(REQUEST_ID_HEADER)
    assert rid is not None and len(rid) > 0
    # uuid4 hex → 32 chars hexadecimales
    assert re.fullmatch(r"[0-9a-f]{32}", rid), f"unexpected request_id format: {rid!r}"


async def test_request_id_se_respeta_si_viene_del_cliente(http_client: AsyncClient) -> None:
    expected = "my-trace-id-123"
    r = await http_client.get("/api/v1/health", headers={REQUEST_ID_HEADER: expected})
    assert r.headers.get(REQUEST_ID_HEADER) == expected
