"""Configuración común de pytest para todos los niveles.

- Asegura que las fixtures async se manejen correctamente (asyncio_mode=auto
  en pyproject.toml).
- Provee un cliente HTTP de la app FastAPI.
"""
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture(autouse=True)
async def _dispose_db_engines_after_test() -> AsyncIterator[None]:
    """Libera el pool de conexiones tras cada test.

    pytest-asyncio en Windows usa un event loop nuevo por test; el engine
    global de SQLAlchemy retendría conexiones del loop anterior y reventaría
    al primer uso del siguiente test. dispose() las cierra dentro del loop
    activo, que sigue vivo en este teardown.
    """
    yield
    from app.infrastructure.persistence import analysis_db, app_db

    await app_db.engine.dispose()
    await analysis_db.engine.dispose()


@pytest.fixture
async def http_client() -> AsyncIterator[AsyncClient]:
    """TestClient sin bootstrap admin (los tests controlan el contenido inicial)."""
    app = create_app(skip_bootstrap=True)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
