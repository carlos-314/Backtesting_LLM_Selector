"""Caso de uso: picks de una semana (F2 §6.4)."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.screening.ports import ScreeningReadPort
from app.domain.screening.read_models import Pick
from app.domain.screening.week_resolver import WeekResolver
from app.domain.shared.week import Week


class WeekNotResolvedError(Exception):
    """La semana solicitada no tiene un run OK (ADR-0004 fail-safe)."""


@dataclass(slots=True)
class GetPicksForWeek:
    reader: ScreeningReadPort

    async def __call__(self, *, week_date_iso: str) -> tuple[Week, list[Pick]]:
        week = Week.from_iso(week_date_iso)
        runs = await self.reader.list_runs_in_period(
            period_start_iso=week_date_iso, period_end_iso=week_date_iso
        )
        resolved = WeekResolver.resolve_weeks(runs)
        if week not in resolved:
            raise WeekNotResolvedError(f"No OK run for week {week}")
        picks = await self.reader.get_picks_for_run(run_id=resolved[week].id)
        return week, picks
