"""Endpoints `/api/v1/weeks/*` y `/api/v1/screening/matrix` (F2 §6.4, ADR-0001)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.screening.get_company import (
    CompanyNotFoundError,
    GetCompany,
)
from app.application.screening.get_matrix import GetMatrix, RangeTooWideError
from app.application.screening.get_picks_for_week import (
    GetPicksForWeek,
    WeekNotResolvedError,
)
from app.application.screening.list_companies import ListCompanies
from app.application.screening.list_weeks import ListWeeks
from app.domain.access.user import User
from app.domain.screening.ports import ScreeningReadPort
from app.infrastructure.analysis_acl.acl_reader import AnalysisAclReader
from app.infrastructure.analysis_acl.exceptions import AnalysisSchemaMismatchError
from app.infrastructure.web.dependencies import (
    get_analysis_session,
    get_current_user,
)
from app.infrastructure.web.errors import ApiError

router = APIRouter(tags=["screening"])


async def get_screening_reader(
    session: AsyncSession = Depends(get_analysis_session),
) -> ScreeningReadPort:
    return AnalysisAclReader(session)


def _map_acl_error(exc: Exception) -> ApiError:
    """Mapea errores de la ACL a ApiError con shape F2 §6.4."""
    if isinstance(exc, AnalysisSchemaMismatchError):
        return ApiError(
            status_code=500,
            code="analysis_schema_mismatch",
            message=str(exc),
        )
    return ApiError(
        status_code=502,
        code="analysis_unreachable",
        message=str(exc),
    )


# ════════════════════════ /weeks ════════════════════════


@router.get("/weeks")
async def list_weeks(
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
    _user: User = Depends(get_current_user),
    reader: ScreeningReadPort = Depends(get_screening_reader),
) -> dict:
    use_case = ListWeeks(reader)
    try:
        items = await use_case(from_iso=from_, to_iso=to)
    except (AnalysisSchemaMismatchError,) as exc:
        raise _map_acl_error(exc) from exc
    return {
        "items": [
            {
                "week_date": str(s.week),
                "run_code": s.run_code,
                "resolved_run_id": s.resolved_run_id,
                "pick_count": s.pick_count,
            }
            for s in items
        ]
    }


# ═════════════════ /weeks/{week_date}/picks ═════════════════


@router.get("/weeks/{week_date}/picks")
async def get_picks(
    week_date: str,
    _user: User = Depends(get_current_user),
    reader: ScreeningReadPort = Depends(get_screening_reader),
) -> dict:
    use_case = GetPicksForWeek(reader)
    try:
        week, picks = await use_case(week_date_iso=week_date)
    except WeekNotResolvedError as exc:
        raise ApiError(status_code=404, code="week_not_found", message=str(exc)) from exc
    except (ValueError,) as exc:
        raise ApiError(status_code=400, code="bad_request", message=str(exc)) from exc
    except AnalysisSchemaMismatchError as exc:
        raise _map_acl_error(exc) from exc

    return {
        "week": str(week),
        "items": [
            {"ticker": str(p.ticker), "role": p.role, "name": p.nombre}
            for p in picks
        ],
    }


# ═══════════════ /weeks/{week_date}/companies ═══════════════


@router.get("/weeks/{week_date}/companies")
async def list_companies(
    week_date: str,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    _user: User = Depends(get_current_user),
    reader: ScreeningReadPort = Depends(get_screening_reader),
) -> dict:
    use_case = ListCompanies(reader)
    try:
        items, next_cursor = await use_case(
            week_date_iso=week_date, limit=limit, cursor=cursor
        )
    except WeekNotResolvedError as exc:
        raise ApiError(status_code=404, code="week_not_found", message=str(exc)) from exc
    except ValueError as exc:
        raise ApiError(status_code=400, code="bad_request", message=str(exc)) from exc
    except AnalysisSchemaMismatchError as exc:
        raise _map_acl_error(exc) from exc

    return {"week": week_date, "items": items, "next_cursor": next_cursor}


# ═════════ /weeks/{week_date}/companies/{ticker} (ficha) ═════════


@router.get("/weeks/{week_date}/companies/{ticker}")
async def get_company(
    week_date: str,
    ticker: str,
    _user: User = Depends(get_current_user),
    reader: ScreeningReadPort = Depends(get_screening_reader),
) -> dict:
    use_case = GetCompany(reader)
    try:
        return await use_case(week_date_iso=week_date, ticker_str=ticker)
    except WeekNotResolvedError as exc:
        raise ApiError(status_code=404, code="week_not_found", message=str(exc)) from exc
    except CompanyNotFoundError as exc:
        raise ApiError(status_code=404, code="company_not_found", message=str(exc)) from exc
    except ValueError as exc:
        raise ApiError(status_code=400, code="bad_request", message=str(exc)) from exc
    except AnalysisSchemaMismatchError as exc:
        raise _map_acl_error(exc) from exc


# ═════════════════════ /screening/matrix ═════════════════════


@router.get("/screening/matrix")
async def get_matrix(
    from_: str = Query(alias="from"),
    to: str = Query(),
    _user: User = Depends(get_current_user),
    reader: ScreeningReadPort = Depends(get_screening_reader),
) -> dict:
    use_case = GetMatrix(reader)
    try:
        return await use_case(from_iso=from_, to_iso=to)
    except RangeTooWideError as exc:
        raise ApiError(status_code=422, code="range_too_wide", message=str(exc)) from exc
    except ValueError as exc:
        raise ApiError(status_code=400, code="bad_request", message=str(exc)) from exc
    except AnalysisSchemaMismatchError as exc:
        raise _map_acl_error(exc) from exc
