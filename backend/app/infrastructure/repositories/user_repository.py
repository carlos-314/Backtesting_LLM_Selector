"""Implementación SQLAlchemy del `UserRepository` (F2 §4.8, §5.1, ADR-0006)."""
from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.access.role import Role
from app.domain.access.user import User
from app.infrastructure.persistence.models.access import AppUser as AppUserModel


def _to_domain(row: AppUserModel) -> User:
    return User(
        id=row.id,
        email=row.email,
        role=Role(row.role),
        is_active=row.is_active,
        full_name=row.full_name,
        google_id=row.google_id,
    )


class SqlUserRepository:
    """Implementa `UserRepository` sobre Postgres + SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, user_id: uuid.UUID) -> User | None:
        row = (
            await self._session.execute(
                select(AppUserModel).where(AppUserModel.id == user_id)
            )
        ).scalar_one_or_none()
        return _to_domain(row) if row else None

    async def find_by_google_id(self, google_id: str) -> User | None:
        row = (
            await self._session.execute(
                select(AppUserModel).where(AppUserModel.google_id == google_id)
            )
        ).scalar_one_or_none()
        return _to_domain(row) if row else None

    async def find_by_email(self, email: str) -> User | None:
        row = (
            await self._session.execute(
                select(AppUserModel).where(AppUserModel.email == email)
            )
        ).scalar_one_or_none()
        return _to_domain(row) if row else None

    async def list_all(self) -> list[User]:
        rows = (
            (await self._session.execute(select(AppUserModel).order_by(AppUserModel.created_at)))
            .scalars()
            .all()
        )
        return [_to_domain(r) for r in rows]

    async def save(self, user: User) -> None:
        """UPSERT por id."""
        stmt = insert(AppUserModel).values(
            id=user.id,
            email=user.email,
            google_id=user.google_id,
            full_name=user.full_name,
            role=user.role.value,
            is_active=user.is_active,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "email": stmt.excluded.email,
                "google_id": stmt.excluded.google_id,
                "full_name": stmt.excluded.full_name,
                "role": stmt.excluded.role,
                "is_active": stmt.excluded.is_active,
            },
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def link_google_id(self, user_id: uuid.UUID, google_id: str) -> None:
        await self._session.execute(
            update(AppUserModel)
            .where(AppUserModel.id == user_id)
            .values(google_id=google_id)
        )
        await self._session.commit()
