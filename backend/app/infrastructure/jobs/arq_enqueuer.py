"""Implementación real del `JobEnqueuer` con arq (ADR-0005).

Mantiene un pool de Redis compartido. La capa de API obtiene el enqueuer
via Depends; el pool se crea perezosamente en la primera invocación.
"""
from __future__ import annotations

from arq import create_pool
from arq.connections import ArqRedis

from app.domain.backtesting.parameters import BacktestId
from app.jobs.worker import WorkerSettings


class ArqJobEnqueuer:
    def __init__(self) -> None:
        self._pool: ArqRedis | None = None

    async def _get_pool(self) -> ArqRedis:
        if self._pool is None:
            self._pool = await create_pool(WorkerSettings.redis_settings)
        return self._pool

    async def enqueue_run_backtest(self, backtest_id: BacktestId) -> None:
        pool = await self._get_pool()
        await pool.enqueue_job("run_backtest", backtest_id)

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.aclose()
            self._pool = None
