"""Caso de uso: lista de semanas resueltas en un periodo (F2 §6.4)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from app.domain.screening.ports import ScreeningReadPort
from app.domain.screening.week_resolver import WeekResolver
from app.domain.shared.week import Week


@dataclass(frozen=True, slots=True)
class WeekSummary:
    week: Week
    run_code: str
    resolved_run_id: int
    pick_count: int


@dataclass(slots=True)
class ListWeeks:
    reader: ScreeningReadPort

    async def __call__(
        self,
        *,
        from_iso: str | None = None,
        to_iso: str | None = None,
    ) -> list[WeekSummary]:
        """Devuelve semanas resueltas en `[from, to]` (inclusive en ambos).

        Si `from`/`to` son None, se calcula un rango amplio (1 año hacia atrás
        / hoy). En cualquier caso `to >= from`.
        """
        today = date.today()
        # Defaults: 1 año hacia atrás
        end_date = (
            Week.from_iso(to_iso).week_date if to_iso else self._monday_of(today)
        )
        start_date = (
            Week.from_iso(from_iso).week_date
            if from_iso
            else self._monday_of(today - timedelta(days=365))
        )
        if start_date > end_date:
            start_date = end_date

        runs = await self.reader.list_runs_in_period(
            period_start_iso=start_date.isoformat(),
            period_end_iso=end_date.isoformat(),
        )
        resolved = WeekResolver.resolve_weeks(runs)
        return sorted(
            [
                WeekSummary(
                    week=w,
                    run_code=run.run_code,
                    resolved_run_id=run.id,
                    pick_count=run.pick_count,
                )
                for w, run in resolved.items()
            ],
            key=lambda s: s.week.week_date,
            reverse=True,  # más recientes primero (perfil visor)
        )

    @staticmethod
    def _monday_of(d: date) -> date:
        return d - timedelta(days=d.weekday())
