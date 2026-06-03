"""VOs base del agregado Backtest (F2 §4.6, §5.2)."""
from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum

from app.domain.shared.money import Money
from app.domain.shared.week import Week

# Type alias para la identidad. F2 §4.6 lo nombra explícitamente como concepto.
BacktestId = uuid.UUID


class BacktestStatus(StrEnum):
    """F2 §5.2: ciclo de vida del agregado.

    Transiciones legales (las hace el agregado, no este enum):
        PENDING  → RUNNING | CANCELLED
        RUNNING  → COMPLETED | FAILED | CANCELLED
        terminal → ∅ (cualquier intento de cambio lanza error)
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in (BacktestStatus.COMPLETED, BacktestStatus.FAILED, BacktestStatus.CANCELLED)


@dataclass(frozen=True, slots=True)
class BacktestParameters:
    """VO inmutable de los parámetros de un backtest (F2 §4.6, §5.2).

    El periodo se expresa en `Week` (F2 §4.3) y no en `date` ambiguo. La
    capa de aplicación convierte las fechas de la API a semanas antes de
    construir esto. El capital inicial y la divisa van juntos en `Money`.
    """

    period_start: Week
    period_end: Week
    initial_capital: Money
    strategy_code: str = "weekly_rotation"
    benchmark_code: str = "buy_and_hold"

    def __post_init__(self) -> None:
        if self.period_end.week_date < self.period_start.week_date:
            raise ValueError(
                f"period_end ({self.period_end}) must be >= period_start ({self.period_start})"
            )
        if self.initial_capital.amount <= 0:
            raise ValueError(f"initial_capital must be positive; got {self.initial_capital}")
        if not self.strategy_code:
            raise ValueError("strategy_code cannot be empty")
        if not self.benchmark_code:
            raise ValueError("benchmark_code cannot be empty")

    @property
    def base_currency(self) -> str:
        return self.initial_capital.currency

    @property
    def weeks_count(self) -> int:
        """Nº de semanas en el periodo (inclusive en ambos extremos)."""
        delta = (self.period_end.week_date - self.period_start.week_date).days
        return delta // 7 + 1

    def iter_weeks(self) -> Iterator[Week]:
        """Itera de `period_start` a `period_end` inclusive, semana a semana."""
        w = self.period_start
        while w.week_date <= self.period_end.week_date:
            yield w
            w = w.next()
