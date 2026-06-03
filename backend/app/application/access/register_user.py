"""Caso de uso: alta de usuario por admin (ADR-0006).

Crea una fila `app_user` con `email + role`, `google_id=NULL`. El primer
login de ese email completará el `google_id`.

Autorización: solo `admin` puede invocarlo. La comprobación se hace aquí
en el caso de uso (no solo en el endpoint), porque es regla del dominio.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.domain.access.exceptions import (
    EmailAlreadyRegisteredError,
    NotPermittedError,
)
from app.domain.access.ports import UserRepository
from app.domain.access.role import Role
from app.domain.access.user import User


@dataclass(slots=True)
class RegisterUser:
    users: UserRepository

    async def __call__(
        self,
        *,
        actor: User,
        email: str,
        role: Role,
    ) -> User:
        if not actor.can_manage_users():
            raise NotPermittedError(
                f"User {actor.email} ({actor.role.value}) cannot register users"
            )
        if not email or "@" not in email:
            raise ValueError(f"Invalid email: {email!r}")

        existing = await self.users.find_by_email(email)
        if existing is not None:
            raise EmailAlreadyRegisteredError(f"{email} is already registered")

        new_user = User(
            id=uuid.uuid4(),
            email=email,
            role=role,
            is_active=True,
            full_name=None,
            google_id=None,  # se vinculará en el primer login
        )
        await self.users.save(new_user)
        return new_user
