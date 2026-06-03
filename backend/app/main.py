"""Punto de entrada FastAPI (F2 §6)."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.application.access.bootstrap_admin import BootstrapInitialAdmin
from app.config import settings
from app.infrastructure.persistence.app_db import SessionFactory
from app.infrastructure.repositories.user_repository import SqlUserRepository
from app.infrastructure.web.errors import install_error_handlers
from app.infrastructure.web.logging import RequestIdMiddleware, configure_logging
from app.infrastructure.web.v1.router import api_v1

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    configure_logging()
    # ADR-0006: bootstrap del admin inicial. Idempotente. Se puede saltar
    # vía `app.state.skip_bootstrap` (usado en tests para controlar el
    # contenido inicial de la BBDD).
    if not getattr(app_instance.state, "skip_bootstrap", False):
        try:
            async with SessionFactory() as session:
                await BootstrapInitialAdmin(SqlUserRepository(session))(
                    settings.INITIAL_ADMIN_EMAIL or None
                )
        except Exception:  # noqa: BLE001 — el arranque no debe morir por esto
            log.exception("bootstrap_initial_admin failed; app continues without admin bootstrap")
    yield


def create_app(*, skip_bootstrap: bool = False) -> FastAPI:
    app = FastAPI(
        title="Backtesting LLM Selector",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.skip_bootstrap = skip_bootstrap

    # Orden importa: el middleware se aplica del último al primero al recibir
    # peticiones; queremos RequestId envolviendo a CORS.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIdMiddleware)

    install_error_handlers(app)
    app.include_router(api_v1)
    return app


app = create_app()
