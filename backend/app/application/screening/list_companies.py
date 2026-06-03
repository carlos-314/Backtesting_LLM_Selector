"""Caso de uso: empresas analizadas en una semana, paginadas (F2 §6.4)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.application.screening.get_picks_for_week import WeekNotResolvedError
from app.domain.screening.ports import ScreeningReadPort
from app.domain.screening.week_resolver import WeekResolver
from app.domain.shared.week import Week
from app.infrastructure.web.v1.cursor import decode_cursor, encode_cursor


@dataclass(slots=True)
class ListCompanies:
    reader: ScreeningReadPort

    async def __call__(
        self,
        *,
        week_date_iso: str,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        if limit <= 0 or limit > 200:
            raise ValueError(f"limit must be in (0, 200]; got {limit}")

        week = Week.from_iso(week_date_iso)
        runs = await self.reader.list_runs_in_period(
            period_start_iso=week_date_iso, period_end_iso=week_date_iso
        )
        resolved = WeekResolver.resolve_weeks(runs)
        if week not in resolved:
            raise WeekNotResolvedError(f"No OK run for week {week}")
        run_id = resolved[week].id

        after_ticker: str | None = None
        if cursor is not None:
            decoded = decode_cursor(cursor)
            after_ticker = decoded.get("after_ticker")

        # Pedimos limit+1 para saber si hay más
        items = await self.reader.list_companies_summary_for_run(
            run_id=run_id, limit=limit + 1, after_ticker=after_ticker
        )
        next_cursor: str | None = None
        if len(items) > limit:
            items = items[:limit]
            next_cursor = encode_cursor({"after_ticker": items[-1]["ticker"]})
        return items, next_cursor
