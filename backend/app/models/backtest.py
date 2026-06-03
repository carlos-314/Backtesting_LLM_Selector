import uuid
from datetime import date, datetime

from sqlalchemy import String, Integer, Boolean, Date, DateTime, Numeric, Text, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    celery_task_id: Mapped[str | None] = mapped_column(String(255))

    # Config (denormalized for immutability)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    initial_capital: Mapped[float] = mapped_column(Numeric(14, 2), default=100000)
    base_currency: Mapped[str] = mapped_column(String(10), default="EUR")
    commission_pct: Mapped[float] = mapped_column(Numeric(6, 4), default=0.001)
    slippage_bps: Mapped[float] = mapped_column(Numeric(6, 4), default=5)
    rebalance_mode: Mapped[str] = mapped_column(String(20), default="composition")
    deduplicate: Mapped[bool] = mapped_column(Boolean, default=True)
    exclude_llm_errors: Mapped[bool] = mapped_column(Boolean, default=True)

    # Benchmarks
    use_equal_weight_bench: Mapped[bool] = mapped_column(Boolean, default=True)
    use_random_bench: Mapped[bool] = mapped_column(Boolean, default=True)
    random_simulations: Mapped[int] = mapped_column(Integer, default=1000)
    external_index_symbol: Mapped[str | None] = mapped_column(String(20))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    snapshots = relationship("BacktestSnapshot", back_populates="run", cascade="all, delete-orphan")
    metrics = relationship("BacktestMetrics", back_populates="run", cascade="all, delete-orphan")


class BacktestSnapshot(Base):
    __tablename__ = "backtest_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("backtest_runs.id", ondelete="CASCADE"), index=True
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_value: Mapped[float] = mapped_column(Numeric(14, 2))
    cash: Mapped[float] = mapped_column(Numeric(14, 2))

    run = relationship("BacktestRun", back_populates="snapshots")
    positions = relationship("BacktestPosition", back_populates="snapshot", cascade="all, delete-orphan")


class BacktestPosition(Base):
    __tablename__ = "backtest_positions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("backtest_snapshots.id", ondelete="CASCADE"), index=True)
    ticker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tickers.id"))
    shares: Mapped[float] = mapped_column(Numeric(14, 4))
    entry_price: Mapped[float] = mapped_column(Numeric(14, 4))
    current_price: Mapped[float] = mapped_column(Numeric(14, 4))
    weight: Mapped[float] = mapped_column(Numeric(6, 4))

    snapshot = relationship("BacktestSnapshot", back_populates="positions")


class BacktestMetrics(Base):
    __tablename__ = "backtest_metrics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("backtest_runs.id", ondelete="CASCADE"), index=True
    )
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    total_return: Mapped[float | None] = mapped_column(Numeric(10, 4))
    cagr: Mapped[float | None] = mapped_column(Numeric(10, 4))
    volatility: Mapped[float | None] = mapped_column(Numeric(10, 4))
    sharpe_ratio: Mapped[float | None] = mapped_column(Numeric(10, 4))
    max_drawdown: Mapped[float | None] = mapped_column(Numeric(10, 4))
    sortino_ratio: Mapped[float | None] = mapped_column(Numeric(10, 4))
    calmar_ratio: Mapped[float | None] = mapped_column(Numeric(10, 4))
    win_rate: Mapped[float | None] = mapped_column(Numeric(10, 4))
    turnover: Mapped[float | None] = mapped_column(Numeric(10, 4))
    pct_random_beaten: Mapped[float | None] = mapped_column(Numeric(10, 4))
    equity_curve: Mapped[dict | None] = mapped_column(JSONB)
    warnings: Mapped[dict | None] = mapped_column(JSONB)

    run = relationship("BacktestRun", back_populates="metrics")
