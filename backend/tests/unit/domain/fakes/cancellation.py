"""Fake del `CancellationToken` (F2 §8.5)."""
from dataclasses import dataclass


@dataclass
class ManualCancellationToken:
    """Cancelación controlada manualmente por el test.

    También permite cancelar tras N consultas (`cancel_after`), útil para
    simular cancelación a mitad del flujo de rotación.
    """

    cancelled: bool = False
    cancel_after: int | None = None
    _calls: int = 0

    async def is_cancelled(self) -> bool:
        self._calls += 1
        if self.cancel_after is not None and self._calls > self.cancel_after:
            return True
        return self.cancelled

    def cancel(self) -> None:
        self.cancelled = True
