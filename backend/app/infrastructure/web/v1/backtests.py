"""Endpoints `/api/v1/backtests/*` (F2 §6.5, ADR-0005, ADR-0007)."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.backtesting.cancel_backtest import (
    CancelBacktest,
    NotCancellableError,
)
from app.application.backtesting.create_backtest import (
    CreateBacktest,
    InvalidCapitalError,
    InvalidPeriodError,
)
from app.application.backtesting.get_backtest import (
    BacktestNotFoundError,
    GetBacktest,
)
from app.application.backtesting.get_result_and_snapshot import (
    BacktestNotReadyError,
    GetBacktestResult,
)
from app.application.backtesting.list_backtests import ListBacktests
from app.domain.access.exceptions import NotPermittedError
from app.domain.access.user import User
from app.domain.backtesting.backtest import Backtest
from app.domain.backtesting.enqueuer import JobEnqueuer
from app.domain.backtesting.ports import BacktestRepositoryPort
from app.infrastructure.repositories.backtest_repository import BacktestRepository
from app.infrastructure.web.dependencies import get_app_session, get_current_user
from app.infrastructure.web.errors import ApiError

router = APIRouter(prefix="/backtests", tags=["backtests"])


# ─────────────────── DI ───────────────────


async def get_backtest_repo(
    session: AsyncSession = Depends(get_app_session),
) -> BacktestRepositoryPort:
    return BacktestRepository(session)


# Lazy-init del singleton arq enqueuer. Override en tests.
_enqueuer_singleton: "JobEnqueuer | None" = None


async def get_job_enqueuer() -> JobEnqueuer:
    global _enqueuer_singleton
    if _enqueuer_singleton is None:
        from app.infrastructure.jobs.arq_enqueuer import ArqJobEnqueuer
        _enqueuer_singleton = ArqJobEnqueuer()
    return _enqueuer_singleton


# ─────────────────── DTOs ───────────────────


class CreateBacktestRequest(BaseModel):
    name: str = Field(min_length=1)
    period_start: date | None = None
    period_end: date | None = None
    initial_capital: Decimal = Decimal("100000")
    base_currency: str = "USD"
    strategy_code: str = "weekly_rotation"
    benchmark_code: str = "buy_and_hold"


def _serialize_backtest(bt: Backtest) -> dict:
    return {
        "id": str(bt.id),
        "name": bt.name,
        "status": bt.status.value,
        "created_by": str(bt.created_by),
        "created_at": bt.created_at.isoformat(),
        "started_at": bt.started_at.isoformat() if bt.started_at else None,
        "completed_at": bt.completed_at.isoformat() if bt.completed_at else None,
        "period": {
            "start": str(bt.parameters.period_start),
            "end": str(bt.parameters.period_end),
        },
        "initial_capital": str(bt.parameters.initial_capital.amount),
        "base_currency": bt.parameters.base_currency,
        "strategy_code": bt.parameters.strategy_code,
        "benchmark_code": bt.parameters.benchmark_code,
        "weeks_total": bt.weeks_total,
        "weeks_processed": bt.weeks_processed,
        "progress": (
            {"weeks_total": bt.weeks_total, "weeks_processed": bt.weeks_processed}
            if bt.weeks_total is not None
            else None
        ),
        "error": (
            {"code": bt.error.code, "message": bt.error.message}
            if bt.error is not None
            else None
        ),
    }


# ════════════════════════ POST /backtests ════════════════════════


@router.post("", status_code=202)
async def create_backtest(
    body: CreateBacktestRequest,
    actor: User = Depends(get_current_user),
    repo: BacktestRepositoryPort = Depends(get_backtest_repo),
    enqueuer: JobEnqueuer = Depends(get_job_enqueuer),
) -> dict:
    use_case = CreateBacktest(repo=repo, enqueuer=enqueuer)
    try:
        bt = await use_case(
            actor=actor,
            name=body.name,
            period_start=body.period_start,
            period_end=body.period_end,
            initial_capital=body.initial_capital,
            base_currency=body.base_currency,
            strategy_code=body.strategy_code,
            benchmark_code=body.benchmark_code,
        )
    except NotPermittedError as exc:
        raise ApiError(status_code=403, code="backtest_not_permitted", message=str(exc)) from exc
    except InvalidPeriodError as exc:
        raise ApiError(status_code=422, code="invalid_period", message=str(exc)) from exc
    except InvalidCapitalError as exc:
        raise ApiError(status_code=422, code="invalid_capital", message=str(exc)) from exc
    return _serialize_backtest(bt)


# ════════════════════════ GET /backtests ════════════════════════


@router.get("")
async def list_backtests(
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    status: str | None = Query(default=None),
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_app_session),
) -> dict:
    use_case = ListBacktests(session=session)
    try:
        items, next_cursor = await use_case(limit=limit, cursor=cursor, status=status)
    except ValueError as exc:
        raise ApiError(status_code=400, code="bad_request", message=str(exc)) from exc
    return {"items": items, "next_cursor": next_cursor}


# ════════════════════════ GET /backtests/{id} ════════════════════════


@router.get("/{backtest_id}")
async def get_backtest_status(
    backtest_id: uuid.UUID,
    _user: User = Depends(get_current_user),
    repo: BacktestRepositoryPort = Depends(get_backtest_repo),
) -> dict:
    use_case = GetBacktest(repo)
    try:
        bt = await use_case(backtest_id)
    except BacktestNotFoundError as exc:
        raise ApiError(status_code=404, code="backtest_not_found", message=str(exc)) from exc
    return _serialize_backtest(bt)


# ════════════════════ POST /backtests/{id}/cancel ════════════════════


@router.post("/{backtest_id}/cancel", status_code=202)
async def cancel_backtest(
    backtest_id: uuid.UUID,
    actor: User = Depends(get_current_user),
    repo: BacktestRepositoryPort = Depends(get_backtest_repo),
) -> dict:
    use_case = CancelBacktest(repo)
    try:
        bt = await use_case(actor=actor, backtest_id=backtest_id)
    except BacktestNotFoundError as exc:
        raise ApiError(status_code=404, code="backtest_not_found", message=str(exc)) from exc
    except NotPermittedError as exc:
        raise ApiError(status_code=403, code="forbidden", message=str(exc)) from exc
    except NotCancellableError as exc:
        raise ApiError(status_code=409, code="not_cancellable", message=str(exc)) from exc
    return _serialize_backtest(bt)


# ════════════════════ GET /backtests/{id}/result ════════════════════


@router.get("/{backtest_id}/result")
async def get_backtest_result(
    backtest_id: uuid.UUID,
    _user: User = Depends(get_current_user),
    repo: BacktestRepositoryPort = Depends(get_backtest_repo),
) -> dict:
    use_case = GetBacktestResult(repo)
    try:
        bt = await use_case(backtest_id)
    except BacktestNotFoundError as exc:
        raise ApiError(status_code=404, code="backtest_not_found", message=str(exc)) from exc
    except BacktestNotReadyError as exc:
        raise ApiError(status_code=409, code="backtest_not_ready", message=str(exc)) from exc

    r = bt.result
    return {
        "metrics": {
            "total_return": str(r.total_return) if r.total_return is not None else None,
            "cagr": str(r.cagr) if r.cagr is not None else None,
            "volatility": str(r.volatility) if r.volatility is not None else None,
            "sharpe": str(r.sharpe) if r.sharpe is not None else None,
            "max_drawdown": str(r.max_drawdown) if r.max_drawdown is not None else None,
        },
        "equity_curve": [
            {"series": pt.series.value, "date": pt.point_date.isoformat(), "value": str(pt.value)}
            for pt in r.equity_curve
        ],
        "snapshot_summary": {
            "weeks": len(bt.snapshot.weeks),
            "first_week": str(bt.snapshot.weeks[0].week) if bt.snapshot.weeks else None,
            "last_week": str(bt.snapshot.weeks[-1].week) if bt.snapshot.weeks else None,
        },
    }


# ════════════════════ GET /backtests/{id}/snapshot ════════════════════


@router.get("/{backtest_id}/snapshot")
async def get_backtest_snapshot(
    backtest_id: uuid.UUID,
    _user: User = Depends(get_current_user),
    repo: BacktestRepositoryPort = Depends(get_backtest_repo),
) -> dict:
    use_case = GetBacktestResult(repo)
    try:
        bt = await use_case(backtest_id)
    except BacktestNotFoundError as exc:
        raise ApiError(status_code=404, code="backtest_not_found", message=str(exc)) from exc
    except BacktestNotReadyError as exc:
        raise ApiError(status_code=409, code="backtest_not_ready", message=str(exc)) from exc

    return {
        "weeks": [
            {
                "week_date": str(w.week),
                "resolved_run_id": w.resolved_run_id,
                "run_code": w.run_code,
                "picks": [
                    {
                        "ticker": str(p.ticker),
                        "ohlc": {
                            "open": str(p.ohlc.open),
                            "high": str(p.ohlc.high),
                            "low": str(p.ohlc.low),
                            "close": str(p.ohlc.close),
                            "currency": p.ohlc.currency,
                        },
                        "fx_pair": p.fx_pair,
                        "fx_rate": str(p.fx_rate) if p.fx_rate is not None else None,
                    }
                    for p in w.picks
                ],
            }
            for w in bt.snapshot.weeks
        ]
    }
