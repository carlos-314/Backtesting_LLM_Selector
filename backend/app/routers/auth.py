import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User, RefreshToken
from app.models.workspace import Workspace, WorkspaceMembership
from app.schemas.auth import GoogleAuthRequest, TokenResponse, RefreshRequest, UserResponse
from app.utils.security import create_access_token, create_refresh_token, hash_token

router = APIRouter()


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:80] + "-" + uuid.uuid4().hex[:6]


@router.post("/google", response_model=TokenResponse)
async def google_login(body: GoogleAuthRequest, db: AsyncSession = Depends(get_db)):
    try:
        idinfo = google_id_token.verify_oauth2_token(
            body.id_token, google_requests.Request(), settings.GOOGLE_CLIENT_ID
        )
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google token")

    email = idinfo["email"]
    google_id = idinfo["sub"]
    full_name = idinfo.get("name", email.split("@")[0])
    avatar_url = idinfo.get("picture")

    # Get or create user
    result = await db.execute(select(User).where(User.google_id == google_id))
    user = result.scalar_one_or_none()

    if not user:
        user = User(email=email, full_name=full_name, google_id=google_id, avatar_url=avatar_url)
        db.add(user)
        await db.flush()

        # Create personal workspace
        slug = _slugify(full_name)
        workspace = Workspace(name=f"{full_name}'s Workspace", slug=slug, owner_id=user.id)
        db.add(workspace)
        await db.flush()

        membership = WorkspaceMembership(workspace_id=workspace.id, user_id=user.id, role="owner")
        db.add(membership)
    else:
        # Update profile info
        user.full_name = full_name
        user.avatar_url = avatar_url

    # Create tokens
    access_token = create_access_token(user.id)
    raw_refresh, hashed_refresh = create_refresh_token()

    refresh = RefreshToken(
        user_id=user.id,
        token_hash=hashed_refresh,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(refresh)

    return TokenResponse(access_token=access_token, refresh_token=raw_refresh)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    hashed = hash_token(body.refresh_token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == hashed,
            RefreshToken.expires_at > datetime.now(timezone.utc),
        )
    )
    existing = result.scalar_one_or_none()
    if not existing:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    # Rotate: delete old, create new
    await db.delete(existing)

    access_token = create_access_token(existing.user_id)
    raw_refresh, hashed_refresh = create_refresh_token()
    new_refresh = RefreshToken(
        user_id=existing.user_id,
        token_hash=hashed_refresh,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(new_refresh)

    return TokenResponse(access_token=access_token, refresh_token=raw_refresh)


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    hashed = hash_token(body.refresh_token)
    await db.execute(delete(RefreshToken).where(RefreshToken.token_hash == hashed))
