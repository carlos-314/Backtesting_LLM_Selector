"""Caso de uso: listar backtests (F2 §6.5)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.backtesting.parameters import BacktestStatus
from app.infrastructure.persistence.models.backtest import (
    Backtest as BacktestModel,
)
from app.infrastructure.web.v1.cursor import decode_cursor, encode_cursor


@dataclass(slots=True)
class ListBacktests:
    """Implementación directa con SQLAlchemy: el listado es operación de
    lectura simple y paginada que no necesita rehidratar agregados
    completos (sin snapshot, sin equity)."""

    session: AsyncSession

    async def __call__(
        self,
        *,
        limit: int = 50,
        cursor: str | None = None,
        status: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        if limit <= 0 or limit > 200:
            raise ValueError(f"limit must be in (0, 200]; got {limit}")
        if status is not None and status not in {s.value for s in BacktestStatus}:
            raise ValueError(f"invalid status filter: {status!r}")

        stmt = select(BacktestModel)
        if status is not None:
            stmt = stmt.where(BacktestModel.status == status)

        if cursor is not None:
            decoded = decode_cursor(cursor)
            cursor_dt = datetime.fromisoformat(decoded["created_at"])
            cursor_id = decoded["id"]
            # Pares (created_at, id) en orden DESC: queremos rows estrictamente
            # menores al cursor.
            stmt = stmt.where(
                (BacktestModel.created_at < cursor_dt)
                | (
                    (BacktestModel.created_at == cursor_dt)
                    & (BacktestModel.id < cursor_id)
                )
            )

        stmt = stmt.order_by(desc(BacktestModel.created_at), desc(BacktestModel.id)).limit(limit + 1)
        rows = (await self.session.execute(stmt)).scalars().all()

        next_cursor: str | None = None
        if len(rows) > limit:
            rows = rows[:limit]
            last = rows[-1]
            next_cursor = encode_cursor({
                "created_at": last.created_at.isoformat(),
                "id": str(last.id),
            })

        items = [
            {
                "id": str(r.id),
                "name": r.name,
                "status": r.status,
                "created_by": str(r.created_by),
                "created_at": r.created_at.isoformat(),
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            }
            for r in rows
        ]
        return items, next_cursor
