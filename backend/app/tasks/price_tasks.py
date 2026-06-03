import uuid

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.ticker import Ticker
from app.services.yahoo_service import fetch_ticker_history, fetch_fx_history
from app.tasks import celery_app

engine = create_engine(settings.DATABASE_URL_SYNC)


@celery_app.task(name="app.tasks.price_tasks.backfill_ticker", bind=True, max_retries=3)
def backfill_ticker(self, ticker_id: str):
    with Session(engine) as db:
        ticker = db.execute(select(Ticker).where(Ticker.id == uuid.UUID(ticker_id))).scalar_one_or_none()
        if not ticker:
            return {"error": "Ticker not found"}
        try:
            rows = fetch_ticker_history(db, ticker)
            return {"ticker": ticker.symbol, "rows": rows}
        except Exception as e:
            raise self.retry(exc=e, countdown=2 ** self.request.retries * 10)


@celery_app.task(name="app.tasks.price_tasks.backfill_new_tickers")
def backfill_new_tickers():
    """Find tickers without price data and trigger backfill."""
    with Session(engine) as db:
        tickers = db.execute(
            select(Ticker).where(Ticker.last_price_update.is_(None))
        ).scalars().all()

        for ticker in tickers:
            backfill_ticker.delay(str(ticker.id))

        return {"queued": len(tickers)}


@celery_app.task(name="app.tasks.price_tasks.daily_price_update")
def daily_price_update():
    """Daily update of all active tickers (Celery Beat at 22:00 UTC)."""
    from datetime import date, timedelta

    with Session(engine) as db:
        tickers = db.execute(
            select(Ticker).where(Ticker.last_price_update.isnot(None))
        ).scalars().all()

        updated = 0
        for ticker in tickers:
            try:
                start = date.today() - timedelta(days=5)
                fetch_ticker_history(db, ticker, start=start)
                updated += 1
            except Exception:
                pass  # Individual failures don't block others

        # Also update FX
        try:
            fetch_fx_history(db, "EURUSD=X", start=date.today() - timedelta(days=5))
            fetch_fx_history(db, "EURCAD=X", start=date.today() - timedelta(days=5))
        except Exception:
            pass

        return {"updated": updated, "total": len(tickers)}
