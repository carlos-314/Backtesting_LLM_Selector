"""Pydantic schemas de la API v1 (request/response).

DTOs (no entidades de dominio). Los endpoints traducen entre dominio y DTO.
"""
from __future__ import annotations

import uuid

from pydantic import BaseModel, EmailStr, Field

from app.domain.access.role import Role
from app.domain.access.user import User


# ───────────────────── User ─────────────────────


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: Role
    full_name: str | None
    is_active: bool

    @classmethod
    def from_domain(cls, user: User) -> "UserResponse":
        return cls(
            id=user.id,
            email=user.email,
            role=user.role,
            full_name=user.full_name,
            is_active=user.is_active,
        )


# ───────────────────── Auth ─────────────────────


class GoogleLoginRequest(BaseModel):
    id_token: str = Field(min_length=1)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # segundos hasta expiración del access_token
    user: UserResponse


# ───────────────────── Admin: registro de usuarios ─────────────────────


class RegisterUserRequest(BaseModel):
    email: EmailStr
    role: Role


class UsersListResponse(BaseModel):
    items: list[UserResponse]
