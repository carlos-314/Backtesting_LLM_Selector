import re
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_workspace_with_role
from app.models.upload import UploadBatch
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.upload import UploadBatchResponse
from app.utils.s3 import upload_file

router = APIRouter()


def _extract_date(filename: str) -> datetime | None:
    match = re.search(r"(\d{8})", filename)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y%m%d").date()
        except ValueError:
            return None
    return None


@router.post("", response_model=UploadBatchResponse, status_code=status.HTTP_201_CREATED)
async def upload_files(
    workspace_id: uuid.UUID,
    xlsx_file: UploadFile = File(...),
    txt_file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    ws_role: tuple[Workspace, str] = Depends(get_workspace_with_role),
    db: AsyncSession = Depends(get_db),
):
    workspace, role = ws_role
    if role == "viewer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Viewers cannot upload files")

    # Validate file types
    if not xlsx_file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="First file must be .xlsx")
    if not txt_file.filename.endswith(".txt"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Second file must be .txt")

    # Extract date from filenames
    xlsx_date = _extract_date(xlsx_file.filename)
    txt_date = _extract_date(txt_file.filename)

    if not xlsx_date or not txt_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot extract date from filenames")

    if xlsx_date != txt_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Date mismatch: xlsx={xlsx_date}, txt={txt_date}",
        )

    week_date = xlsx_date

    # If duplicate exists, delete old batch (cascades to signals, selections, dossiers)
    result = await db.execute(
        select(UploadBatch).where(
            UploadBatch.workspace_id == workspace_id,
            UploadBatch.week_date == week_date,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        await db.delete(existing)
        await db.flush()

    # Validate file sizes (max 10MB each)
    xlsx_data = await xlsx_file.read()
    txt_data = await txt_file.read()
    if len(xlsx_data) > 10 * 1024 * 1024 or len(txt_data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File size exceeds 10MB limit")

    # Upload to S3
    prefix = f"{workspace_id}/{week_date}"
    xlsx_key = upload_file(f"{prefix}/{xlsx_file.filename}", xlsx_data,
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    txt_key = upload_file(f"{prefix}/{txt_file.filename}", txt_data, "text/plain")

    # Create batch record
    batch = UploadBatch(
        workspace_id=workspace_id,
        uploaded_by=user.id,
        week_date=week_date,
        xlsx_s3_key=xlsx_key,
        txt_s3_key=txt_key,
        status="pending",
    )
    db.add(batch)
    await db.flush()

    # Dispatch Celery task
    from app.tasks.parse_tasks import parse_upload_batch
    parse_upload_batch.delay(str(batch.id))

    return batch


@router.get("", response_model=list[UploadBatchResponse])
async def list_uploads(
    workspace_id: uuid.UUID,
    ws_role: tuple[Workspace, str] = Depends(get_workspace_with_role),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UploadBatch)
        .where(UploadBatch.workspace_id == workspace_id)
        .order_by(UploadBatch.week_date.desc())
    )
    return result.scalars().all()


@router.get("/{batch_id}", response_model=UploadBatchResponse)
async def get_upload(
    workspace_id: uuid.UUID,
    batch_id: uuid.UUID,
    ws_role: tuple[Workspace, str] = Depends(get_workspace_with_role),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UploadBatch).where(
            UploadBatch.id == batch_id,
            UploadBatch.workspace_id == workspace_id,
        )
    )
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload batch not found")
    return batch


@router.delete("/{batch_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_upload(
    workspace_id: uuid.UUID,
    batch_id: uuid.UUID,
    ws_role: tuple[Workspace, str] = Depends(get_workspace_with_role),
    db: AsyncSession = Depends(get_db),
):
    _, role = ws_role
    if role == "viewer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Viewers cannot delete uploads")

    result = await db.execute(
        select(UploadBatch).where(
            UploadBatch.id == batch_id,
            UploadBatch.workspace_id == workspace_id,
        )
    )
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload batch not found")

    await db.delete(batch)
