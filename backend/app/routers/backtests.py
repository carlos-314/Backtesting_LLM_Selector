import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_workspace_with_role
from app.models.backtest import BacktestRun, BacktestMetrics
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.backtest import (
    BacktestCreate, BacktestRunResponse, BacktestDetailResponse,
    MetricsResponse, CompareResponse,
)

router = APIRouter()


@router.post("", response_model=BacktestRunResponse, status_code=status.HTTP_201_CREATED)
async def create_backtest(
    workspace_id: uuid.UUID,
    body: BacktestCreate,
    user: User = Depends(get_current_user),
    ws_role: tuple[Workspace, str] = Depends(get_workspace_with_role),
    db: AsyncSession = Depends(get_db),
):
    _, role = ws_role
    if role == "viewer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Viewers cannot create backtests")

    run = BacktestRun(
        workspace_id=workspace_id,
        created_by=user.id,
        name=body.name,
        start_date=body.start_date,
        end_date=body.end_date,
        initial_capital=body.initial_capital,
        commission_pct=body.commission_pct,
        slippage_bps=body.slippage_bps,
        rebalance_mode=body.rebalance_mode,
        deduplicate=body.deduplicate,
        exclude_llm_errors=body.exclude_llm_errors,
        use_equal_weight_bench=body.use_equal_weight_bench,
        use_random_bench=body.use_random_bench,
        random_simulations=body.random_simulations,
        external_index_symbol=body.external_index_symbol,
        status="queued",
    )
    db.add(run)
    await db.flush()

    # Dispatch Celery task
    from app.tasks.backtest_tasks import run_backtest
    task = run_backtest.delay(str(run.id))
    run.celery_task_id = task.id

    return run


@router.get("", response_model=list[BacktestRunResponse])
async def list_backtests(
    workspace_id: uuid.UUID,
    ws_role: tuple[Workspace, str] = Depends(get_workspace_with_role),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BacktestRun)
        .where(BacktestRun.workspace_id == workspace_id)
        .order_by(BacktestRun.created_at.desc())
    )
    return result.scalars().all()


@router.get("/compare", response_model=CompareResponse)
async def compare_backtests(
    workspace_id: uuid.UUID,
    ids: str = Query(..., description="Comma-separated run IDs"),
    ws_role: tuple[Workspace, str] = Depends(get_workspace_with_role),
    db: AsyncSession = Depends(get_db),
):
    run_ids = [uuid.UUID(rid.strip()) for rid in ids.split(",")]
    if len(run_ids) < 2 or len(run_ids) > 4:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Compare 2-4 runs")

    runs = []
    all_metrics = []
    for rid in run_ids:
        result = await db.execute(
            select(BacktestRun).where(
                BacktestRun.id == rid, BacktestRun.workspace_id == workspace_id
            )
        )
        run = result.scalar_one_or_none()
        if not run:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run {rid} not found")
        runs.append(run)

        metrics_result = await db.execute(
            select(BacktestMetrics).where(BacktestMetrics.run_id == rid)
        )
        all_metrics.append(metrics_result.scalars().all())

    return CompareResponse(runs=runs, metrics=all_metrics)


@router.get("/{backtest_id}", response_model=BacktestDetailResponse)
async def get_backtest(
    workspace_id: uuid.UUID,
    backtest_id: uuid.UUID,
    ws_role: tuple[Workspace, str] = Depends(get_workspace_with_role),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BacktestRun).where(
            BacktestRun.id == backtest_id,
            BacktestRun.workspace_id == workspace_id,
        )
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backtest not found")

    metrics_result = await db.execute(
        select(BacktestMetrics).where(BacktestMetrics.run_id == backtest_id)
    )
    metrics = metrics_result.scalars().all()

    return BacktestDetailResponse(run=run, metrics=metrics)


@router.delete("/{backtest_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_backtest(
    workspace_id: uuid.UUID,
    backtest_id: uuid.UUID,
    ws_role: tuple[Workspace, str] = Depends(get_workspace_with_role),
    db: AsyncSession = Depends(get_db),
):
    _, role = ws_role
    if role not in ("owner", "member"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    result = await db.execute(
        select(BacktestRun).where(
            BacktestRun.id == backtest_id,
            BacktestRun.workspace_id == workspace_id,
        )
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backtest not found")
    await db.delete(run)
