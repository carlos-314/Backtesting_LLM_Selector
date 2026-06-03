"""Caso de uso: cancelar un backtest (F2 §6.5)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.application.backtesting.get_backtest import BacktestNotFoundError
from app.domain.access.exceptions import NotPermittedError
from app.domain.access.user import User
from app.domain.backtesting.backtest import Backtest, InvalidStateTransition
from app.domain.backtesting.parameters import BacktestId
from app.domain.backtesting.ports import BacktestRepositoryPort


class NotCancellableError(Exception):
    """El backtest ya está en estado terminal (F2 §6.5)."""


@dataclass(slots=True)
class CancelBacktest:
    repo: BacktestRepositoryPort

    async def __call__(self, *, actor: User, backtest_id: BacktestId) -> Backtest:
        bt = await self.repo.get(backtest_id)
        if bt is None:
            raise BacktestNotFoundError(f"Backtest {backtest_id} not found")

        # F2 §6.5: "Requiere ser el creador o analyst"
        if not actor.can_cancel_backtest(created_by=bt.created_by):
            raise NotPermittedError(
                f"User {actor.email} cannot cancel backtests"
            )

        try:
            bt.cancel(when=datetime.now(timezone.utc))
        except InvalidStateTransition as exc:
            raise NotCancellableError(str(exc)) from exc

        await self.repo.save(bt)
        return bt
