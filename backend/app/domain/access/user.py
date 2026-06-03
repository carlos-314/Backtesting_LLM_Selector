"""Entidad `User` (F2 §4.6, §5.1).

VO inmutable que combina identidad + rol + estado. Las **capacidades**
(¿puede crear backtests? ¿puede gestionar usuarios?) se derivan del rol;
NO se almacenan, evitando estado inconsistente (F2 §5.1).

La autorización efectiva se hace en backend: la API consulta estas
capacidades antes de ejecutar la operación (F1 §5).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.domain.access.role import Role


@dataclass(frozen=True, slots=True)
class User:
    id: uuid.UUID
    email: str
    role: Role
    is_active: bool = True
    full_name: str | None = None
    google_id: str | None = None  # None = pre-alta sin login todavía (ADR-0006)

    def __post_init__(self) -> None:
        if not self.email:
            raise ValueError("User.email cannot be empty")
        if not isinstance(self.role, Role):
            raise TypeError(f"User.role must be a Role; got {type(self.role).__name__}")

    # ─────────────────────── Capacidades (F2 §5.1) ───────────────────────

    def can_create_backtest(self) -> bool:
        """`analyst` o `admin`. F2 §5.1 (auditoría I2)."""
        return self.is_active and self.role in (Role.ANALYST, Role.ADMIN)

    def can_cancel_backtest(self, *, created_by: uuid.UUID) -> bool:
        """F2 §6.5: "ser el creador o analyst".

        Implementación día uno: cualquier `analyst`/`admin` activo puede
        cancelar cualquier backtest; el creador `viewer` no puede cancelar
        ni los suyos (los crea un `analyst` por restricción).
        """
        del created_by  # no se usa día uno; F2 lo prevé para reforzar después
        return self.is_active and self.role in (Role.ANALYST, Role.ADMIN)

    def can_manage_users(self) -> bool:
        """`admin`. ADR-0006."""
        return self.is_active and self.role == Role.ADMIN

    # ─────────────────────── Vinculación de google_id ───────────────────────

    def is_linked(self) -> bool:
        """¿Ya hizo login alguna vez (google_id vinculado)?"""
        return self.google_id is not None
