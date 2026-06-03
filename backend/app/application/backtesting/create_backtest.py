"""Caso de uso: crear un backtest (F2 §6.5).

Valida → crea agregado pending → guarda → encola job → devuelve.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.domain.access.exceptions import NotPermittedError
from app.domain.access.user import User
from app.domain.backtesting.backtest import Backtest
from app.domain.backtesting.enqueuer import JobEnqueuer
from app.domain.backtesting.parameters import BacktestParameters
from app.domain.backtesting.ports import BacktestRepositoryPort
from app.domain.shared.money import Money
from app.domain.shared.week import Week


class InvalidPeriodError(ValueError):
    """Periodo inválido (start>end o sin semanas)."""


class InvalidCapitalError(ValueError):
    """initial_capital <= 0."""


@dataclass(slots=True)
class CreateBacktest:
    repo: BacktestRepositoryPort
    enqueuer: JobEnqueuer

    async def __call__(
        self,
        *,
        actor: User,
        name: str,
        period_start: date | None = None,
        period_end: date | None = None,
        initial_capital: Decimal = Decimal("100000"),
        base_currency: str = "USD",
        strategy_code: str = "weekly_rotation",
        benchmark_code: str = "buy_and_hold",
    ) -> Backtest:
        if not actor.can_create_backtest():
            raise NotPermittedError(
                f"User {actor.email} ({actor.role.value}) cannot create backtests"
            )

        if initial_capital <= 0:
            raise InvalidCapitalError(f"initial_capital must be positive; got {initial_capital}")

        if period_start is None or period_end is None:
            # Default: 26 semanas hacia atrás (F3 §1.3)
            today = date.today()
            today_monday = today - timedelta(days=today.weekday())
            period_end = period_end or today_monday
            period_start = period_start or (today_monday - timedelta(weeks=26))

        try:
            ws = Week(_to_monday(period_start))
            we = Week(_to_monday(period_end))
        except ValueError as exc:
            raise InvalidPeriodError(str(exc)) from exc
        if ws.week_date > we.week_date:
            raise InvalidPeriodError(
                f"period_start ({ws}) must be <= period_end ({we})"
            )

        try:
            params = BacktestParameters(
                period_start=ws,
                period_end=we,
                initial_capital=Money(initial_capital, base_currency),
                strategy_code=strategy_code,
                benchmark_code=benchmark_code,
            )
        except ValueError as exc:
            raise InvalidPeriodError(str(exc)) from exc

        bt = Backtest(
            id=uuid.uuid4(),
            name=name,
            created_by=actor.id,
            parameters=params,
            created_at=datetime.now(timezone.utc),
        )
        await self.repo.save(bt)
        await self.enqueuer.enqueue_run_backtest(bt.id)
        return bt


def _to_monday(d: date) -> date:
    """Redondea hacia atrás al lunes de la semana del calendario."""
    return d - timedelta(days=d.weekday())
