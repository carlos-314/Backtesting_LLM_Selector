"""Adapter del `CancellationToken` que consulta la BBDD (F2 §6.5).

Mecanismo de cancelación día uno: el endpoint `POST /backtests/{id}/cancel`
muta el agregado a `cancelled` y guarda. El worker detecta el cambio
consultando el `status` actual del backtest entre semanas.

Coste: una query SELECT por semana procesada. A la escala (decenas de
semanas por backtest), trivial. La alternativa (Redis pub/sub) introduce
otra pieza operativa que F2 no exige día uno.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.backtesting.parameters import BacktestId, BacktestStatus
from app.infrastructure.persistence.models.backtest import Backtest as BacktestModel


class DbCancellationToken:
    """Implementa `CancellationToken` consultando el status persistido."""

    def __init__(self, session: AsyncSession, backtest_id: BacktestId) -> None:
        self._session = session
        self._id = backtest_id

    async def is_cancelled(self) -> bool:
        stmt = select(BacktestModel.status).where(BacktestModel.id == self._id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return row == BacktestStatus.CANCELLED.value
