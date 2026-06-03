"""Snapshot de reproducibilidad (F2 §5.3).

Copia congelada de lo que un backtest usó: semanas → run resuelto → picks con
OHLC y FX. No tiene FKs a la BBDD de análisis (es otra base; la copia ES la
reproducibilidad). Cascadeable desde `backtest`.
"""
import uuid
from decimal import Decimal

from sqlalchemy import (
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.app_db import Base


class BacktestSnapshotWeek(Base):
    """Una fila por semana del backtest (F2 §5.3)."""

    __tablename__ = "backtest_snapshot_week"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    backtest_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("backtest.id", ondelete="CASCADE"),
        nullable=False,
    )
    week_date: Mapped["Date"] = mapped_column(Date, nullable=False)
    # Copia del id_run externo, **sin FK** (otra base). Es la prueba de
    # reproducibilidad si el pipeline externo cambia.
    resolved_run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    run_code: Mapped[str | None] = mapped_column(String, nullable=True)

    __table_args__ = (
        UniqueConstraint("backtest_id", "week_date", name="uq_snapshot_week_backtest_date"),
        Index("ix_snapshot_week_backtest_id", "backtest_id"),
    )


class BacktestSnapshotPick(Base):
    """Picks congelados de cada semana, con OHLC y FX usados (F2 §5.3)."""

    __tablename__ = "backtest_snapshot_pick"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_week_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("backtest_snapshot_week.id", ondelete="CASCADE"),
        nullable=False,
    )
    ticker: Mapped[str] = mapped_column(String, nullable=False)
    # OHLC completo: F2 §5.3 lo justifica por estrategias futuras (stops, trailing).
    open: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    fx_pair: Mapped[str | None] = mapped_column(String, nullable=True)
    fx_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)

    __table_args__ = (
        UniqueConstraint("snapshot_week_id", "ticker", name="uq_snapshot_pick_week_ticker"),
        Index("ix_snapshot_pick_snapshot_week_id", "snapshot_week_id"),
    )
