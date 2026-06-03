"""arq WorkerSettings (ADR-0005).

Configuración del worker arq. Las tareas se importan y se listan en
`WorkerSettings.functions`. `cron_jobs` queda vacío día uno — costura para
el refresco programado de precios (F1 §5).
"""
from arq.connections import RedisSettings

from app.config import settings
from app.jobs.run_backtest import run_backtest


def _redis_settings_from_url(url: str) -> RedisSettings:
    """Parsea `redis://host:port/db` a RedisSettings de arq."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=int(parsed.path.lstrip("/") or 0),
        password=parsed.password,
    )


class WorkerSettings:
    """Configuración del worker arq."""

    redis_settings = _redis_settings_from_url(settings.REDIS_URL)
    functions = [run_backtest]
    cron_jobs: list = []  # Costura del scheduler (F1 §5). Vacío día uno.
