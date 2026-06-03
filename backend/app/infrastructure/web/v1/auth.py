"""Endpoints `/api/v1/auth/*` (F2 §6.3, ADR-0007)."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, status
from fastapi.responses import Response

from app.application.access.authenticate_with_google import AuthenticateWithGoogle
from app.config import settings
from app.domain.access.exceptions import (
    GoogleUnreachableError,
    InvalidGoogleTokenError,
    UserNotAuthorizedError,
)
from app.domain.access.ports import GoogleIdentityVerifier, UserRepository
from app.domain.access.user import User
from app.infrastructure.identity.security import create_access_token
from app.infrastructure.web.dependencies import (
    get_current_user,
    get_google_verifier,
    get_user_repo,
)
from app.infrastructure.web.errors import ApiError
from app.infrastructure.web.v1.schemas import (
    GoogleLoginRequest,
    LoginResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])
log = logging.getLogger(__name__)


@router.post("/google", response_model=LoginResponse)
async def google_login(
    body: GoogleLoginRequest,
    verifier: GoogleIdentityVerifier = Depends(get_google_verifier),
    users: UserRepository = Depends(get_user_repo),
) -> LoginResponse:
    use_case = AuthenticateWithGoogle(verifier, users)
    try:
        user = await use_case(body.id_token)
    except InvalidGoogleTokenError as exc:
        raise ApiError(
            status_code=401, code="invalid_google_token", message=str(exc)
        ) from exc
    except UserNotAuthorizedError as exc:
        raise ApiError(
            status_code=403, code="user_not_authorized", message=str(exc)
        ) from exc
    except GoogleUnreachableError as exc:
        raise ApiError(
            status_code=502, code="google_unreachable", message=str(exc)
        ) from exc

    access_token = create_access_token(user.id)
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.from_domain(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.from_domain(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(_user: User = Depends(get_current_user)) -> Response:
    """ADR-0007: stateless — el cliente borra su token. Aquí solo
    validamos el bearer (401 si inválido) y devolvemos 204."""
    return Response(status_code=status.HTTP_204_NO_CONTENT)
