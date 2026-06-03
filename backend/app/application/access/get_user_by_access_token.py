"""Caso de uso: resolver el `User` actual a partir del JWT (F2 §6.3).

Decodifica el access_token JWT (firmado por nosotros, no por Google) y
busca el `User` por `id`. Devuelve `None` si:
- el token es inválido o ha expirado,
- el `user_id` no existe,
- el user está inactivo.

Útil para `GET /auth/me` y para la dependencia FastAPI `require_user`.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from app.domain.access.ports import UserRepository
from app.domain.access.user import User
from app.infrastructure.identity.security import decode_access_token

log = logging.getLogger(__name__)


@dataclass(slots=True)
class GetUserByAccessToken:
    users: UserRepository

    async def __call__(self, access_token: str) -> User | None:
        try:
            payload = decode_access_token(access_token)
            user_id = uuid.UUID(payload["sub"])
        except Exception as exc:  # noqa: BLE001 — JWT failures are diverse
            log.info("get_user_by_access_token: invalid token (%s)", type(exc).__name__)
            return None

        user = await self.users.find_by_id(user_id)
        if user is None or not user.is_active:
            return None
        return user
