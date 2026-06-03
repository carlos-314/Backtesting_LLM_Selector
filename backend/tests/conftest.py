"""Configuración común de pytest para todos los niveles.

**Aislamiento de BBDD de tests** (decisión registrada en MEMORY):
- La BBDD de la app propia para tests es `backtesting_app_test`, distinta
  de la `backtesting_app` que usa el dev. Se fuerza vía `APP_DATABASE_URL`
  ANTES de importar `app` para que `Settings()` resuelva al valor de test.
- El schema se crea con `Base.metadata.create_all()` una vez por sesión
  pytest (no usamos Alembic en tests para ir rápido; las migraciones se
  prueban con `alembic upgrade head` en CI sobre `backtesting_app`).
- La BBDD de análisis de test (`backtesting_analysis_test`) ya estaba
  aislada desde la pieza 6; los tests crean el schema legacy mínimo.
"""
from __future__ import annotations

# CRÍTICO: setear el env ANTES de importar `app.*` para que `Settings()` resuelva
# correctamente. `pydantic-settings` prioriza os.environ > .env file > defaults.
import os

os.environ["APP_DATABASE_URL"] = (
    "postgresql+asyncpg://backtesting:backtesting_dev@localhost:55432/backtesting_app_test"
)
# Para tests no queremos que el bootstrap del admin inicial se dispare
# accidentalmente — los tests usan `skip_bootstrap=True` pero por defensa
# en profundidad vaciamos la variable.
os.environ["INITIAL_ADMIN_EMAIL"] = ""

from collections.abc import AsyncIterator  # noqa: E402

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from app.config import settings  # noqa: E402
from app.infrastructure.persistence.app_db import Base  # noqa: E402
from app.infrastructure.persistence import models  # noqa: F401, E402 — registra modelos en Base.metadata
from app.main import create_app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
async def _create_schema_once() -> AsyncIterator[None]:
    """Crea las 8 tablas de F2 §5 en `backtesting_app_test` al inicio de la
    sesión pytest. Usa un engine LOCAL (no el global) para evitar que sus
    conexiones queden ligadas a un loop session-scope mientras los tests
    usan loops function-scope (RuntimeError 'different loop')."""
    local_engine = create_async_engine(settings.APP_DATABASE_URL, future=True)
    try:
        async with local_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    finally:
        await local_engine.dispose()
    yield


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
