"""Endpoints `/api/v1/admin/users` (ADR-0006).

Solo accesibles para `admin` (capability `can_manage_users`).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.application.access.register_user import RegisterUser
from app.domain.access.exceptions import EmailAlreadyRegisteredError, NotPermittedError
from app.domain.access.ports import UserRepository
from app.domain.access.user import User
from app.infrastructure.web.dependencies import get_user_repo, require_admin
from app.infrastructure.web.errors import ApiError
from app.infrastructure.web.v1.schemas import (
    RegisterUserRequest,
    UserResponse,
    UsersListResponse,
)

router = APIRouter(prefix="/admin/users", tags=["admin"])


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_user(
    body: RegisterUserRequest,
    actor: User = Depends(require_admin),
    users: UserRepository = Depends(get_user_repo),
) -> UserResponse:
    use_case = RegisterUser(users)
    try:
        created = await use_case(actor=actor, email=body.email, role=body.role)
    except NotPermittedError as exc:
        # Defensa en profundidad: require_admin ya lo bloquearía, pero el
        # caso de uso lo verifica también.
        raise ApiError(status_code=403, code="forbidden", message=str(exc)) from exc
    except EmailAlreadyRegisteredError as exc:
        raise ApiError(
            status_code=409, code="email_already_registered", message=str(exc)
        ) from exc
    return UserResponse.from_domain(created)


@router.get("", response_model=UsersListResponse)
async def list_users(
    _actor: User = Depends(require_admin),
    users: UserRepository = Depends(get_user_repo),
) -> UsersListResponse:
    items = await users.list_all()
    return UsersListResponse(items=[UserResponse.from_domain(u) for u in items])
