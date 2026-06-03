"""Caché de precios y FX (F2 §5.4).

"Feeds, no FK": el snapshot copia el precio usado, no lo referencia. Purgar la
caché jamás rompe un backtest pasado (F2 §5.4).
"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, Identity, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.app_db import Base


class PriceCacheDaily(Base):
    """OHLC + adj_close + volume descargado de yfinance (F2 §5.4)."""

    __tablename__ = "price_cache_daily"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    ticker: Mapped[str] = mapped_column(String, nullable=False)
    price_date: Mapped["Date"] = mapped_column(Date, nullable=False)
    open: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    high: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    low: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    close: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    adj_close: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False, server_default="yfinance")
    fetched_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("ticker", "price_date", name="uq_price_cache_ticker_date"),
    )


class FxDaily(Base):
    """Tipos de cambio diarios (F2 §5.4)."""

    __tablename__ = "fx_daily"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    pair: Mapped[str] = mapped_column(String, nullable=False)
    date: Mapped["Date"] = mapped_column(Date, nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False, server_default="yfinance")
    fetched_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("pair", "date", name="uq_fx_daily_pair_date"),
    )
