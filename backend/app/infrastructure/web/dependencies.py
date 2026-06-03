"""Dependencias FastAPI compartidas (F2 §6.1, ADR-0007).

Cableado de capas:
- Sesiones de BBDD (propia + análisis).
- Repositorios.
- Verificador Google.
- `get_current_user` extrae el bearer y devuelve el `User`.
- `require_capability` controla autorización en backend (F1 §5).
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.access.get_user_by_access_token import GetUserByAccessToken
from app.config import settings
from app.domain.access.ports import GoogleIdentityVerifier, UserRepository
from app.domain.access.user import User
from app.infrastructure.identity.google_verifier import GoogleIdentityVerifierImpl
from app.infrastructure.persistence.app_db import SessionFactory as AppSessionFactory
from app.infrastructure.persistence.analysis_db import (
    SessionFactory as AnalysisSessionFactory,
)
from app.infrastructure.repositories.user_repository import SqlUserRepository
from app.infrastructure.web.errors import ApiError

bearer_scheme = HTTPBearer(auto_error=False)


# ───────────────────── Sesiones ─────────────────────


async def get_app_session() -> AsyncIterator[AsyncSession]:
    async with AppSessionFactory() as s:
        yield s


async def get_analysis_session() -> AsyncIterator[AsyncSession]:
    async with AnalysisSessionFactory() as s:
        try:
            yield s
        finally:
            await s.rollback()  # read-only


# ───────────────────── Adaptadores ─────────────────────


async def get_user_repo(
    session: AsyncSession = Depends(get_app_session),
) -> UserRepository:
    return SqlUserRepository(session)


async def get_google_verifier() -> GoogleIdentityVerifier:
    return GoogleIdentityVerifierImpl(settings.GOOGLE_CLIENT_ID)


# ───────────────────── Identidad ─────────────────────


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    users: UserRepository = Depends(get_user_repo),
) -> User:
    """Devuelve el `User` actual a partir del bearer. Lanza 401 si no hay
    sesión válida (token ausente, malformado, expirado, user inactivo)."""
    if credentials is None or not credentials.credentials:
        raise ApiError(
            status_code=401, code="unauthorized", message="Missing bearer token"
        )
    use_case = GetUserByAccessToken(users)
    user = await use_case(credentials.credentials)
    if user is None:
        raise ApiError(
            status_code=401, code="unauthorized", message="Invalid or expired token"
        )
    return user


def require_capability(capability: str) -> Callable[..., object]:
    """Factory de dependencias que valida una capacidad del `User`.

    Uso:
        @router.get(...)
        async def x(user = Depends(require_capability("can_manage_users"))):
            ...
    """

    async def check(user: User = Depends(get_current_user)) -> User:
        cap_fn = getattr(user, capability, None)
        if cap_fn is None or not callable(cap_fn) or not cap_fn():
            raise ApiError(
                status_code=403,
                code="forbidden",
                message=f"Capability {capability!r} required",
            )
        return user

    return check


require_admin = require_capability("can_manage_users")
require_analyst_or_admin = require_capability("can_create_backtest")
