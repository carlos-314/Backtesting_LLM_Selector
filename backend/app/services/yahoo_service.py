import time
from datetime import date, datetime, timedelta, timezone

import yfinance as yf
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.ticker import Ticker, TickerPrice, FxDaily

# Canadian tickers that need .TO suffix on Yahoo Finance
CANADIAN_SUFFIXES = {"CSU", "DSGX", "MRU", "WN", "DOL", "ATD", "BN", "BAM", "TRI"}


def yahoo_symbol(symbol: str, exchange: str | None = None) -> str:
    """Map internal symbol to Yahoo Finance symbol."""
    if exchange and exchange.upper() in ("TSX", "TSE", "TO"):
        return f"{symbol}.TO"
    if symbol in CANADIAN_SUFFIXES:
        return f"{symbol}.TO"
    return symbol


def fetch_ticker_history(
    db: Session,
    ticker: Ticker,
    start: date | None = None,
    end: date | None = None,
    max_retries: int = 3,
) -> int:
    """Fetch OHLCV history from Yahoo and upsert into ticker_prices. Returns rows upserted."""
    ysymbol = yahoo_symbol(ticker.symbol, ticker.exchange)
    if not start:
        start = date.today() - timedelta(days=365 * 10)
    if not end:
        end = date.today()

    for attempt in range(max_retries):
        try:
            data = yf.download(
                ysymbol,
                start=start.isoformat(),
                end=end.isoformat(),
                auto_adjust=False,
                progress=False,
            )
            break
        except Exception:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)

    if data.empty:
        return 0

    # yfinance may return multi-level columns for single ticker — flatten
    if hasattr(data.columns, "nlevels") and data.columns.nlevels > 1:
        data.columns = data.columns.get_level_values(0)

    def _float(val):
        if val is None:
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    def _int(val):
        if val is None:
            return None
        try:
            return int(float(val))
        except (TypeError, ValueError):
            return None

    rows_upserted = 0
    for idx, row in data.iterrows():
        price_date = idx.date() if hasattr(idx, "date") else idx

        values = {
            "ticker_id": ticker.id,
            "date": price_date,
            "open": _float(row.get("Open")),
            "high": _float(row.get("High")),
            "low": _float(row.get("Low")),
            "close": _float(row.get("Close")),
            "adj_close": _float(row.get("Adj Close")),
            "volume": _int(row.get("Volume")),
        }

        stmt = pg_insert(TickerPrice).values(**values).on_conflict_do_update(
            index_elements=["ticker_id", "date"],
            set_={k: v for k, v in values.items() if k not in ("ticker_id", "date")},
        )
        db.execute(stmt)
        rows_upserted += 1

    ticker.last_price_update = datetime.now(timezone.utc)
    db.commit()
    return rows_upserted


def fetch_fx_history(db: Session, pair: str = "EURUSD=X", start: date | None = None, end: date | None = None) -> int:
    """Fetch FX rate history from Yahoo. Returns rows upserted."""
    if not start:
        start = date.today() - timedelta(days=365 * 10)
    if not end:
        end = date.today()

    data = yf.download(pair, start=start.isoformat(), end=end.isoformat(), progress=False)
    if data.empty:
        return 0

    if hasattr(data.columns, "nlevels") and data.columns.nlevels > 1:
        data.columns = data.columns.get_level_values(0)

    rows = 0
    for idx, row in data.iterrows():
        price_date = idx.date() if hasattr(idx, "date") else idx
        try:
            rate = float(row.get("Close"))
        except (TypeError, ValueError):
            rate = None
        if rate is None:
            continue

        stmt = pg_insert(FxDaily).values(
            pair=pair, date=price_date, rate=rate,
        ).on_conflict_do_update(
            index_elements=["pair", "date"],
            set_={"rate": rate},
        )
        db.execute(stmt)
        rows += 1

    db.commit()
    return rows
