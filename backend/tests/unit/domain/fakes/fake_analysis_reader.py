"""Fake del `AnalysisReadPort` (F2 §8.5, §8.7)."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.screening.read_models import AnalysisRun, Pick


@dataclass
class FakeAnalysisReader:
    runs: list[AnalysisRun] = field(default_factory=list)
    picks_by_run: dict[int, list[Pick]] = field(default_factory=dict)

    def add_run(self, run: AnalysisRun, picks: list[Pick]) -> None:
        self.runs.append(run)
        self.picks_by_run[run.id] = picks

    async def list_runs_in_period(
        self, *, period_start_iso: str, period_end_iso: str
    ) -> list[AnalysisRun]:
        # El fake ignora el filtro temporal — los tests preparan los runs que
        # necesitan. Si algún día queremos probar el filtrado, se añade aquí.
        return list(self.runs)

    async def get_picks_for_run(self, *, run_id: int) -> list[Pick]:
        return list(self.picks_by_run.get(run_id, []))
