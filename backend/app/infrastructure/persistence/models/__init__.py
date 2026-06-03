"""Registro de modelos en `Base.metadata` (F2 §5).

Importar este paquete asegura que Alembic ve las 8 tablas para autogenerate.
"""
from app.infrastructure.persistence.models.access import AppUser
from app.infrastructure.persistence.models.backtest import (
    Backtest,
    BacktestEquityPoint,
    BacktestResult,
)
from app.infrastructure.persistence.models.cache import FxDaily, PriceCacheDaily
from app.infrastructure.persistence.models.snapshot import (
    BacktestSnapshotPick,
    BacktestSnapshotWeek,
)

__all__ = [
    "AppUser",
    "Backtest",
    "BacktestEquityPoint",
    "BacktestResult",
    "BacktestSnapshotPick",
    "BacktestSnapshotWeek",
    "FxDaily",
    "PriceCacheDaily",
]
