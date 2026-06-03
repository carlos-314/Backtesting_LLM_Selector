"""Fake en memoria del `BacktestRepositoryPort` (F2 §8.5, §8.7)."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.backtesting.backtest import Backtest
from app.domain.backtesting.parameters import BacktestId


@dataclass
class InMemoryBacktestRepo:
    """Guarda el agregado por id. No serializa: guarda la referencia tal cual."""

    _store: dict[BacktestId, Backtest] = field(default_factory=dict)

    async def save(self, backtest: Backtest) -> None:
        self._store[backtest.id] = backtest

    async def get(self, backtest_id: BacktestId) -> Backtest | None:
        return self._store.get(backtest_id)

    def all(self) -> list[Backtest]:
        """Helper de inspección para los tests."""
        return list(self._store.values())
