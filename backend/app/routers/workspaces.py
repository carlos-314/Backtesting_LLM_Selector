import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_workspace_with_role
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMembership
from app.schemas.workspace import (
    WorkspaceCreate, WorkspaceResponse, MemberInvite, MemberResponse, MemberRoleUpdate,
)

router = APIRouter()


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:80] + "-" + uuid.uuid4().hex[:6]


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    body: WorkspaceCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    workspace = Workspace(name=body.name, slug=_slugify(body.name), owner_id=user.id)
    db.add(workspace)
    await db.flush()

    membership = WorkspaceMembership(workspace_id=workspace.id, user_id=user.id, role="owner")
    db.add(membership)
    await db.flush()

    return workspace


@router.get("", response_model=list[WorkspaceResponse])
async def list_workspaces(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Workspace)
        .join(WorkspaceMembership, Workspace.id == WorkspaceMembership.workspace_id)
        .where(WorkspaceMembership.user_id == user.id)
        .order_by(Workspace.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    ws_role: tuple[Workspace, str] = Depends(get_workspace_with_role),
):
    workspace, _ = ws_role
    return workspace


@router.get("/{workspace_id}/members", response_model=list[MemberResponse])
async def list_members(
    workspace_id: uuid.UUID,
    ws_role: tuple[Workspace, str] = Depends(get_workspace_with_role),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WorkspaceMembership, User)
        .join(User, WorkspaceMembership.user_id == User.id)
        .where(WorkspaceMembership.workspace_id == workspace_id)
    )
    members = []
    for membership, user in result.all():
        members.append(MemberResponse(
            id=membership.id,
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=membership.role,
        ))
    return members


@router.post("/{workspace_id}/members", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
async def invite_member(
    workspace_id: uuid.UUID,
    body: MemberInvite,
    ws_role: tuple[Workspace, str] = Depends(get_workspace_with_role),
    db: AsyncSession = Depends(get_db),
):
    _, role = ws_role
    if role != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owners can invite members")

    if body.role not in ("member", "viewer"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")

    result = await db.execute(select(User).where(User.email == body.email))
    target_user = result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found. They must sign in first.")

    # Check if already a member
    result = await db.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == target_user.id,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already a member")

    membership = WorkspaceMembership(workspace_id=workspace_id, user_id=target_user.id, role=body.role)
    db.add(membership)
    await db.flush()

    return MemberResponse(
        id=membership.id, user_id=target_user.id,
        email=target_user.email, full_name=target_user.full_name, role=membership.role,
    )


@router.patch("/{workspace_id}/members/{user_id}")
async def update_member_role(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    body: MemberRoleUpdate,
    ws_role: tuple[Workspace, str] = Depends(get_workspace_with_role),
    db: AsyncSession = Depends(get_db),
):
    _, role = ws_role
    if role != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owners can change roles")

    result = await db.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user_id,
        )
    )
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    membership.role = body.role
    return {"status": "updated"}


@router.delete("/{workspace_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    ws_role: tuple[Workspace, str] = Depends(get_workspace_with_role),
    db: AsyncSession = Depends(get_db),
):
    workspace, role = ws_role
    if role != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owners can remove members")

    if user_id == workspace.owner_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove workspace owner")

    result = await db.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user_id,
        )
    )
    membership = result.scalar_one_or_none()
    if membership:
        await db.delete(membership)
