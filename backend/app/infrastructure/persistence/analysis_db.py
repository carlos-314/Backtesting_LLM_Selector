"""Engine de la BBDD de análisis (solo lectura, F1 §4.3 / F2 §9.2).

La protección física vive en las grants del user `app_reader` en Railway
(ver ADR-0004 y memoria del proyecto). Aquí solo se configura el engine.
"""
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

# `pool_pre_ping=True` evita conexiones zombies tras inactividad (Railway tiende
# a cerrarlas). Sin pool sería catastrófico en e2e + worker.
engine = create_async_engine(
    settings.ANALYSIS_DATABASE_URL or "postgresql+asyncpg://disabled:disabled@localhost:1/disabled",
    echo=False,
    future=True,
    pool_pre_ping=True,
)

SessionFactory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_analysis_session() -> AsyncIterator[AsyncSession]:
    """Dependencia FastAPI: sesión async read-only contra la BBDD de análisis."""
    async with SessionFactory() as session:
        # No commit (read-only); rollback explícito por si algo intenta escribir.
        try:
            yield session
        finally:
            await session.rollback()
