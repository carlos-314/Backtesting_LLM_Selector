"""Logging correlacionado por request_id (F2 §7.1).

Implementa el correlator para peticiones HTTP. El correlator de jobs
(`backtest.id`) vive en `app/jobs/` y se enchufa en piezas posteriores.
"""
import logging
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)

HEADER = "X-Request-ID"


def get_request_id() -> str | None:
    """Devuelve el request_id activo (o None fuera de petición)."""
    return _request_id_ctx.get()


class RequestIdFilter(logging.Filter):
    """Inyecta `request_id` en cada LogRecord (placeholder `%(request_id)s`)."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id_ctx.get() or "-"
        return True


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Lee `X-Request-ID` o genera uno; lo expone en contextvar y header."""

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get(HEADER) or uuid.uuid4().hex
        token = _request_id_ctx.set(rid)
        try:
            response: Response = await call_next(request)
        finally:
            _request_id_ctx.reset(token)
        response.headers[HEADER] = rid
        return response


def configure_logging() -> None:
    """Configuración mínima de logging estructurado-friendly.

    Día uno: formato plano con `request_id`. Pasar a JSON estructurado cuando
    se monten métricas (F1 §5, capa en costura).
    """
    root = logging.getLogger()
    if root.handlers:
        # Evitar añadir handlers duplicados (uvicorn los pone también).
        for h in root.handlers:
            h.addFilter(RequestIdFilter())
        return

    handler = logging.StreamHandler()
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] req=%(request_id)s %(name)s: %(message)s")
    )
    root.addHandler(handler)
    root.setLevel(logging.INFO)
