from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery("backtester")
celery_app.conf.update(
    broker_url=settings.REDIS_URL,
    result_backend=settings.REDIS_URL,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_routes={
        "app.tasks.parse_tasks.*": {"queue": "parse"},
        "app.tasks.price_tasks.*": {"queue": "prices"},
        "app.tasks.backtest_tasks.*": {"queue": "backtest"},
    },
    beat_schedule={
        "daily-price-update": {
            "task": "app.tasks.price_tasks.daily_price_update",
            "schedule": crontab(hour=22, minute=0),
        },
    },
)

# Import tasks so they register
from app.tasks import parse_tasks, price_tasks, backtest_tasks  # noqa: E402, F401
