"""Puertos del contexto Acceso (F2 §4.8, §7.3, ADR-0006)."""
from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from app.domain.access.google_identity import GoogleIdentity
from app.domain.access.user import User


@runtime_checkable
class GoogleIdentityVerifier(Protocol):
    """Frontera de Google (F2 §7.3). El único sitio del backend que conoce
    la API de Google. Mockeable en tests (F2 §8.5)."""

    async def verify(self, id_token: str) -> GoogleIdentity:
        """Verifica un `id_token` y devuelve la identidad.

        Lanza:
          - `InvalidGoogleTokenError` si el token es inválido/expirado.
          - `GoogleUnreachableError` si Google no está disponible.
        """
        ...


@runtime_checkable
class UserRepository(Protocol):
    """Persistencia de `User` (ADR-0006)."""

    async def find_by_id(self, user_id: uuid.UUID) -> User | None:
        ...

    async def find_by_google_id(self, google_id: str) -> User | None:
        ...

    async def find_by_email(self, email: str) -> User | None:
        ...

    async def list_all(self) -> list[User]:
        """Listado para la futura UI de admin (F0). Día uno usado por
        `bootstrap_initial_admin` para saber si hay admins."""
        ...

    async def save(self, user: User) -> None:
        """Crea o actualiza un user. Idempotente por `user.id`."""
        ...

    async def link_google_id(self, user_id: uuid.UUID, google_id: str) -> None:
        """Vincula `google_id` a un usuario pre-aprobado en el primer login."""
        ...
