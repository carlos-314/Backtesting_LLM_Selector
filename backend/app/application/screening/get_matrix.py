"""Caso de uso: matriz histórica de selección (ADR-0001 propuesta)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.screening.ports import ScreeningReadPort
from app.domain.screening.week_resolver import WeekResolver
from app.domain.shared.ticker import TickerSymbol
from app.domain.shared.week import Week

MAX_WEEKS = 156  # ADR-0001


class RangeTooWideError(Exception):
    """El rango excede el tope de semanas (ADR-0001)."""


@dataclass(slots=True)
class GetMatrix:
    reader: ScreeningReadPort

    async def __call__(
        self, *, from_iso: str, to_iso: str
    ) -> dict[str, Any]:
        start_week = Week.from_iso(from_iso)
        end_week = Week.from_iso(to_iso)
        if start_week.week_date > end_week.week_date:
            raise ValueError("from must be <= to")

        n_weeks = (end_week.week_date - start_week.week_date).days // 7 + 1
        if n_weeks > MAX_WEEKS:
            raise RangeTooWideError(
                f"Range exceeds {MAX_WEEKS} weeks; got {n_weeks}"
            )

        # 1) Resolver semanas
        runs = await self.reader.list_runs_in_period(
            period_start_iso=from_iso, period_end_iso=to_iso
        )
        resolved = WeekResolver.resolve_weeks(runs)
        ordered_weeks = sorted(
            (w for w in resolved if start_week.week_date <= w.week_date <= end_week.week_date),
            key=lambda w: w.week_date,
        )

        # 2) Para cada semana, obtener universo + picks
        cells: list[dict[str, Any]] = []
        all_tickers: set[TickerSymbol] = set()
        weeks_out: list[dict[str, Any]] = []

        for week in ordered_weeks:
            run = resolved[week]
            weeks_out.append({
                "week_date": str(week),
                "run_code": run.run_code,
                "resolved_run_id": run.id,
            })
            universe = await self.reader.list_universe_for_run(run_id=run.id)
            picks = await self.reader.get_picks_for_run(run_id=run.id)
            picked_set = {p.ticker for p in picks}
            for tk in universe:
                all_tickers.add(tk)
                state = "selected" if tk in picked_set else "in_universe"
                cells.append({
                    "ticker": str(tk),
                    "week_date": str(week),
                    "state": state,
                })

        # 3) Metadata catálogo
        metadata = await self.reader.get_companies_metadata(
            tickers=sorted(all_tickers, key=lambda t: t.value)
        )
        companies_out = [
            {
                "ticker": str(tk),
                "name": metadata.get(tk, {}).get("name"),
                "country": metadata.get(tk, {}).get("country"),
                "currency": metadata.get(tk, {}).get("currency"),
                "exchange": metadata.get(tk, {}).get("exchange"),
            }
            for tk in sorted(all_tickers, key=lambda t: t.value)
        ]

        return {
            "weeks": weeks_out,
            "companies": companies_out,
            "cells": cells,
        }
