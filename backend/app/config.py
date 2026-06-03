from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings

ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"

LOCAL_APP_DB_URL = (
    "postgresql+asyncpg://backtesting:backtesting_dev@localhost:55432/backtesting_app"
)


class Settings(BaseSettings):
    APP_DATABASE_URL: str = LOCAL_APP_DB_URL
    ANALYSIS_DATABASE_URL: str = ""

    REDIS_URL: str = "redis://localhost:6379/0"

    JWT_SECRET: str = "dev-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    GOOGLE_CLIENT_ID: str = ""

    # Bootstrap del primer admin (ADR-0006). Si la tabla `app_user` está
    # vacía al arrancar, se inserta un user con este email y role=admin.
    # Sin él, la primera vez nadie puede entrar. Una vez creado, esta
    # variable se ignora.
    INITIAL_ADMIN_EMAIL: str = ""

    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    model_config = {"env_file": str(ROOT_ENV), "extra": "ignore"}

    @field_validator("APP_DATABASE_URL", mode="before")
    @classmethod
    def _app_db_default(cls, v: str | None) -> str:
        # Contrato del .env: si la variable está vacía/ausente, usar la BBDD
        # local levantada con `docker compose up -d postgres`.
        return v or LOCAL_APP_DB_URL


settings = Settings()
