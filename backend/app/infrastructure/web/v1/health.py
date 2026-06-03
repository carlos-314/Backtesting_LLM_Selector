"""GET /api/v1/health — F2 §6.2.

Sin autenticación. Comprueba conectividad con ambas BBDD. yfinance NO se
chequea aquí (su salud se infiere de los backtests, F2 §6.2).
"""
import logging
from typing import Literal

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.infrastructure.persistence.app_db import engine as app_engine
from app.infrastructure.persistence.analysis_db import engine as analysis_engine

router = APIRouter()
log = logging.getLogger(__name__)

CheckStatus = Literal["ok", "degraded"]


async def _ping(engine, name: str) -> CheckStatus:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return "ok"
    except Exception as exc:  # noqa: BLE001 — diagnose, do not propagate
        log.warning("health.%s.degraded: %s", name, exc)
        return "degraded"


@router.get("/health", include_in_schema=True, tags=["meta"])
async def health() -> JSONResponse:
    db_app = await _ping(app_engine, "db_app")
    db_analysis = await _ping(analysis_engine, "db_analysis")

    overall_ok = db_app == "ok" and db_analysis == "ok"
    payload = {
        "status": "ok" if overall_ok else "degraded",
        "checks": {"db_app": db_app, "db_analysis": db_analysis},
    }
    code = status.HTTP_200_OK if overall_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=code, content=payload)
