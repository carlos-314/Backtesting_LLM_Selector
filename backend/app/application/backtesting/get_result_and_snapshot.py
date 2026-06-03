"""Casos de uso: result y snapshot del backtest (F2 §6.5)."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.backtesting.get_backtest import BacktestNotFoundError
from app.domain.backtesting.backtest import Backtest
from app.domain.backtesting.parameters import BacktestId, BacktestStatus
from app.domain.backtesting.ports import BacktestRepositoryPort


class BacktestNotReadyError(Exception):
    """`409 backtest_not_ready` — F2 §6.5: distingue 'no existe' de 'aún no'."""


@dataclass(slots=True)
class GetBacktestResult:
    repo: BacktestRepositoryPort

    async def __call__(self, backtest_id: BacktestId) -> Backtest:
        bt = await self.repo.get(backtest_id)
        if bt is None:
            raise BacktestNotFoundError(f"Backtest {backtest_id} not found")
        if bt.status != BacktestStatus.COMPLETED:
            raise BacktestNotReadyError(
                f"Backtest is in status {bt.status.value!r}, not completed"
            )
        return bt
