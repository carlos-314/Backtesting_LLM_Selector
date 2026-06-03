"""Resultado del backtest (F2 §5.2).

`BacktestResult` agrupa las métricas núcleo + curvas de equity (cartera vs
benchmark). El criterio de columna vs `metrics_extra` (F2 §5.2 auditoría M2):
"si se filtra, ordena o grafica por ella va a columna; si es informativa, a
metrics_extra".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any


class EquitySeries(StrEnum):
    PORTFOLIO = "portfolio"
    BENCHMARK = "benchmark"


@dataclass(frozen=True, slots=True)
class EquityPoint:
    """Un punto de la curva de equity (F2 §5.2)."""

    series: EquitySeries
    point_date: date
    value: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.value, Decimal):
            raise TypeError(f"EquityPoint.value must be Decimal; got {type(self.value).__name__}")


@dataclass(frozen=True, slots=True)
class BacktestResult:
    """Métricas núcleo + curvas (F2 §5.2)."""

    total_return: Decimal | None = None
    cagr: Decimal | None = None
    volatility: Decimal | None = None
    sharpe: Decimal | None = None
    max_drawdown: Decimal | None = None
    equity_curve: tuple[EquityPoint, ...] = field(default_factory=tuple)
    metrics_extra: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.equity_curve, tuple):
            raise TypeError("equity_curve must be a tuple (immutable)")
        # Orden temporal por (series, point_date) — se permite cualquier orden
        # de entrada pero verificamos que dentro de cada serie esté ordenada.
        per_series: dict[EquitySeries, list[date]] = {}
        for pt in self.equity_curve:
            per_series.setdefault(pt.series, []).append(pt.point_date)
        for series, dates in per_series.items():
            if dates != sorted(dates):
                raise ValueError(
                    f"equity_curve for series {series.value!r} must be in chronological order"
                )
            if len(set(dates)) != len(dates):
                raise ValueError(
                    f"equity_curve for series {series.value!r} has duplicate dates"
                )
