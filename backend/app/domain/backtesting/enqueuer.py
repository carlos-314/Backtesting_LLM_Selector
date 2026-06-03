"""Puerto `JobEnqueuer` (ADR-0005).

El endpoint `POST /backtests` crea el agregado y encola un job. El backend
no espera a que termine: devuelve `202` con `pending` (F2 §6.5).

Aquí solo definimos el puerto. La implementación real usa arq (con pool
Redis). En tests, un fake en memoria registra las llamadas para verificar
que el endpoint encoló.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.backtesting.parameters import BacktestId


@runtime_checkable
class JobEnqueuer(Protocol):
    async def enqueue_run_backtest(self, backtest_id: BacktestId) -> None:
        ...
