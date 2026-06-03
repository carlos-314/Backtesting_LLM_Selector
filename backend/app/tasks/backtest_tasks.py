import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.backtest import BacktestRun
from app.services.backtest_engine import BacktestEngine
from app.tasks import celery_app

engine = create_engine(settings.DATABASE_URL_SYNC)


@celery_app.task(name="app.tasks.backtest_tasks.run_backtest", bind=True, max_retries=1)
def run_backtest(self, run_id: str):
    run_uuid = uuid.UUID(run_id)

    with Session(engine) as db:
        run = db.execute(select(BacktestRun).where(BacktestRun.id == run_uuid)).scalar_one_or_none()
        if not run:
            return {"error": "Run not found"}

        run.status = "running"
        db.commit()

        try:
            engine_bt = BacktestEngine(run, db)
            engine_bt.execute()

            run.status = "complete"
            run.completed_at = datetime.now(timezone.utc)
            db.commit()

            return {"status": "complete", "run_id": run_id}

        except Exception as e:
            run.status = "failed"
            run.completed_at = datetime.now(timezone.utc)
            db.commit()
            raise self.retry(exc=e, countdown=60)
