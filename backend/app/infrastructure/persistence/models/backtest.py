"""Modelos del agregado Backtest (F2 §5.2).

Tres tablas que viven dentro de la frontera del agregado:
- `backtest` (raíz: parámetros + ciclo de vida)
- `backtest_result` (1:1, existe solo si completed)
- `backtest_equity_point` (serie temporal, append-only)
"""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import DATERANGE, JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.app_db import Base

ALLOWED_STATUSES = ("pending", "running", "completed", "failed", "cancelled")
_STATUSES_SQL = "(" + ", ".join(f"'{s}'" for s in ALLOWED_STATUSES) + ")"

ALLOWED_SERIES = ("portfolio", "benchmark")
_SERIES_SQL = "(" + ", ".join(f"'{s}'" for s in ALLOWED_SERIES) + ")"


class Backtest(Base):
    """Raíz del agregado (F2 §5.2)."""

    __tablename__ = "backtest"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("app_user.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    # DATERANGE: la integridad inicio ≤ fin la hace el propio tipo Postgres
    # cuando el rango se construye en formato [start, end].
    period = mapped_column(DATERANGE, nullable=False)
    initial_capital: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    base_currency: Mapped[str] = mapped_column(String, nullable=False, server_default="USD")
    strategy_code: Mapped[str] = mapped_column(String, nullable=False)
    benchmark_code: Mapped[str] = mapped_column(String, nullable=False)

    # Progreso honesto por semanas (F2 §5.2, auditoría C1/M1).
    weeks_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weeks_processed: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # `{code, message, context}` del fallo (F2 §5.2). NULL salvo `failed`.
    error_detail = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(f"status IN {_STATUSES_SQL}", name="ck_backtest_status"),
        CheckConstraint("initial_capital > 0", name="ck_backtest_initial_capital_positive"),
        # F2 §5.2: "CHECK no vacío (inicio ≤ fin en la base)" se garantiza ya por
        # el constructor del DATERANGE (Postgres rechaza rangos invertidos);
        # añadimos chequeo explícito de no-empty por claridad.
        CheckConstraint("NOT isempty(period)", name="ck_backtest_period_not_empty"),
        # Índices F2 §5.5
        Index("ix_backtest_status", "status"),
        Index("ix_backtest_created_by", "created_by"),
        Index("ix_backtest_created_at_desc", "created_at", postgresql_ops={"created_at": "DESC"}),
    )


class BacktestResult(Base):
    """Resultado, 1:1 con Backtest. PK=FK garantiza unicidad (F2 §5.2)."""

    __tablename__ = "backtest_result"

    backtest_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("backtest.id", ondelete="CASCADE"),
        primary_key=True,
    )
    total_return: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    cagr: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    volatility: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    sharpe: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    max_drawdown: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    metrics_extra = mapped_column(JSONB, nullable=True)


class BacktestEquityPoint(Base):
    """Serie temporal append-only (F2 §5.2)."""

    __tablename__ = "backtest_equity_point"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    backtest_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("backtest.id", ondelete="CASCADE"),
        nullable=False,
    )
    series: Mapped[str] = mapped_column(String, nullable=False)
    point_date: Mapped["Date"] = mapped_column(Date, nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    __table_args__ = (
        CheckConstraint(f"series IN {_SERIES_SQL}", name="ck_equity_point_series"),
        # UNIQUE compuesto cubre el patrón "lectura por serie ordenada por fecha"
        # (F2 §5.5). El UNIQUE crea el índice.
        UniqueConstraint(
            "backtest_id", "series", "point_date", name="uq_equity_point_backtest_series_date"
        ),
    )
