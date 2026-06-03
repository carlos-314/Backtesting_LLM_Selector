"""Engine de la BBDD propia (lectura-escritura). F2 §5."""
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """Base declarativa de los modelos de la BBDD propia (F2 §5)."""


engine = create_async_engine(settings.APP_DATABASE_URL, echo=False, future=True)

SessionFactory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_app_session() -> AsyncIterator[AsyncSession]:
    """Dependencia FastAPI: sesión async transaccional contra la BBDD propia."""
    async with SessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
