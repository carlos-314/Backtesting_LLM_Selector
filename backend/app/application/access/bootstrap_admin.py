"""Caso de uso: bootstrap del admin inicial (ADR-0006).

Idempotente: si ya hay AL MENOS UN admin en la BBDD, no hace nada. Si no
hay ninguno y se proporciona `INITIAL_ADMIN_EMAIL`, crea un user con
`role=admin, google_id=NULL`. El primer login de ese email completa el
vínculo.

Se invoca en el `lifespan` de FastAPI (pieza 11).
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from app.domain.access.ports import UserRepository
from app.domain.access.role import Role
from app.domain.access.user import User

log = logging.getLogger(__name__)


@dataclass(slots=True)
class BootstrapInitialAdmin:
    users: UserRepository

    async def __call__(self, initial_admin_email: str | None) -> User | None:
        """Devuelve el user creado, o `None` si no hizo nada."""
        if not initial_admin_email:
            log.info("bootstrap_admin: INITIAL_ADMIN_EMAIL not set, skipping")
            return None

        all_users = await self.users.list_all()
        if any(u.role == Role.ADMIN for u in all_users):
            log.info("bootstrap_admin: an admin already exists, skipping")
            return None

        # Si existe el email pero con otro role, lo respetamos: NO sobreescribimos.
        # En ese caso, no hay admin: el operador debe arreglar el estado a mano.
        if any(u.email == initial_admin_email for u in all_users):
            log.warning(
                "bootstrap_admin: email %s exists but with non-admin role; "
                "manual intervention required",
                initial_admin_email,
            )
            return None

        admin = User(
            id=uuid.uuid4(),
            email=initial_admin_email,
            role=Role.ADMIN,
            is_active=True,
            full_name=None,
            google_id=None,
        )
        await self.users.save(admin)
        log.info("bootstrap_admin: created initial admin %s", initial_admin_email)
        return admin
