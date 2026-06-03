"""Casos de uso de lectura del backtest (F2 §6.5)."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.backtesting.backtest import Backtest
from app.domain.backtesting.parameters import BacktestId
from app.domain.backtesting.ports import BacktestRepositoryPort


class BacktestNotFoundError(Exception):
    pass


@dataclass(slots=True)
class GetBacktest:
    repo: BacktestRepositoryPort

    async def __call__(self, backtest_id: BacktestId) -> Backtest:
        bt = await self.repo.get(backtest_id)
        if bt is None:
            raise BacktestNotFoundError(f"Backtest {backtest_id} not found")
        return bt
