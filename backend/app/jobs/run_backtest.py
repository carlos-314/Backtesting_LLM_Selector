"""Tarea arq `run_backtest` (F2 §4.9, ADR-0005).

Orquesta el ciclo de vida del backtest fuera del request-response:
1. Carga el agregado del repo (debe existir y estar PENDING).
2. Cablea adaptadores (ACL, price provider, repositorio, token).
3. Invoca `BacktestEngine.run()` — muta el agregado in-memory.
4. Persiste el estado final del agregado.

Errores no atrapados (red caída, BBDD muerta) → propagan, arq reintenta
según su política (no exploramos retries día uno; el engine ya distingue
sus fallos esperados como `failed`).

Esta función es invocable directamente en tests (sin arq runtime) pasando
un `ctx` mínimo con el `backtest_id`.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.domain.backtesting.engine import BacktestEngine
from app.domain.backtesting.parameters import BacktestId, BacktestStatus
from app.domain.backtesting.strategy import WeeklyRotationStrategy
from app.infrastructure.analysis_acl.acl_reader import AnalysisAclReader
from app.infrastructure.persistence.analysis_db import (
    SessionFactory as AnalysisSessionFactory,
)
from app.infrastructure.persistence.app_db import SessionFactory as AppSessionFactory
from app.infrastructure.price_provider.cached_price_provider import CachedPriceProvider
from app.infrastructure.price_provider.yfinance_client import YfinanceClient
from app.infrastructure.price_provider.yfinance_client_impl import YfinanceClientImpl
from app.infrastructure.repositories.backtest_repository import BacktestRepository
from app.infrastructure.repositories.db_cancellation_token import DbCancellationToken

log = logging.getLogger(__name__)


async def run_backtest(
    ctx: dict[str, Any],
    backtest_id: BacktestId,
    *,
    # `yfinance_client` se pasa solo en tests; en runtime arq usa el default.
    yfinance_client: YfinanceClient | None = None,
) -> None:
    """Ejecuta un backtest identificado por su id.

    `ctx` es el contexto que arq pasa al invocar la tarea. Lo ignoramos por
    ahora; queda disponible para acceder a `ctx['job_id']` cuando lo
    queramos correlacionar en logs (F2 §7.1).
    """
    client: YfinanceClient = yfinance_client or YfinanceClientImpl()

    # Dos sesiones (BBDD propia + análisis) — vivimos en el worker, no hay
    # FastAPI Depends que las inyecte.
    async with AppSessionFactory() as app_session, AnalysisSessionFactory() as analysis_session:
        repo = BacktestRepository(app_session)
        bt = await repo.get(backtest_id)
        if bt is None:
            log.warning("run_backtest: backtest_id=%s not found, skipping", backtest_id)
            return

        if bt.status != BacktestStatus.PENDING:
            log.info(
                "run_backtest: backtest_id=%s status=%s, not pending — skipping",
                backtest_id, bt.status.value,
            )
            return

        acl = AnalysisAclReader(analysis_session)
        prices = CachedPriceProvider(app_session, client)
        token = DbCancellationToken(app_session, backtest_id)
        strategy = WeeklyRotationStrategy()
        engine = BacktestEngine(analysis=acl, prices=prices, strategy=strategy)

        now = datetime.now(timezone.utc)
        await engine.run(bt, now=now, cancellation=token)

        # Si el endpoint cancel ya guardó CANCELLED en BBDD mientras el engine
        # estaba corriendo Y el engine detectó la cancelación, ahora bt
        # in-memory está en CANCELLED igualmente. Save es idempotente.
        await repo.save(bt)

        log.info(
            "run_backtest: backtest_id=%s finished status=%s",
            backtest_id, bt.status.value,
        )
