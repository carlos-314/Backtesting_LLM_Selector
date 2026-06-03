"""Caso de uso: login con Google (F2 §6.3, ADR-0006).

Flujo:
1. Verificar `id_token` con Google → `GoogleIdentity`.
2. Buscar usuario por `google_id`:
   - Si existe e is_active → emitir tokens.
   - Si existe e !is_active → `UserNotAuthorizedError`.
3. Si no, buscar por `email`:
   - Si existe con `google_id IS NULL` (pre-alta) → vincular y emitir tokens.
   - Si existe con `google_id` distinto → `UserNotAuthorizedError`
     (el email pertenece a otra cuenta Google ya vinculada).
4. Si no existe ni por `google_id` ni por `email` → `UserNotAuthorizedError`.

La emisión de tokens (JWT access + refresh) es responsabilidad del caller
(la capa de API), no de este caso de uso. Aquí devolvemos sólo el `User`
ya autenticado.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.access.exceptions import UserNotAuthorizedError
from app.domain.access.ports import GoogleIdentityVerifier, UserRepository
from app.domain.access.user import User


@dataclass(slots=True)
class AuthenticateWithGoogle:
    verifier: GoogleIdentityVerifier
    users: UserRepository

    async def __call__(self, id_token: str) -> User:
        identity = await self.verifier.verify(id_token)

        # 1) ¿Ya vinculado por google_id?
        existing = await self.users.find_by_google_id(identity.google_id)
        if existing is not None:
            if not existing.is_active:
                raise UserNotAuthorizedError(
                    f"User {existing.email} is inactive"
                )
            return existing

        # 2) ¿Pre-alta por email?
        by_email = await self.users.find_by_email(identity.email)
        if by_email is None:
            raise UserNotAuthorizedError(
                f"Email {identity.email} is not on the access list"
            )
        if by_email.google_id is not None:
            # Email vinculado a otra cuenta Google ya
            raise UserNotAuthorizedError(
                f"Email {identity.email} is linked to a different Google account"
            )
        if not by_email.is_active:
            raise UserNotAuthorizedError(
                f"User {identity.email} is inactive"
            )

        # 3) Vincular y devolver el user con google_id
        await self.users.link_google_id(by_email.id, identity.google_id)
        from dataclasses import replace
        return replace(by_email, google_id=identity.google_id)
