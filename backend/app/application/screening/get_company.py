"""Caso de uso: ficha de una empresa en una semana (F2 §6.4, ADR-0002 R2-bis)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.application.screening.get_picks_for_week import WeekNotResolvedError
from app.domain.screening.ports import ScreeningReadPort
from app.domain.screening.week_resolver import WeekResolver
from app.domain.shared.ticker import TickerSymbol
from app.domain.shared.week import Week


class CompanyNotFoundError(Exception):
    """La empresa pedida no está en el run de esa semana."""


@dataclass(slots=True)
class GetCompany:
    reader: ScreeningReadPort

    async def __call__(
        self, *, week_date_iso: str, ticker_str: str
    ) -> dict[str, Any]:
        week = Week.from_iso(week_date_iso)
        ticker = TickerSymbol.of(ticker_str)

        runs = await self.reader.list_runs_in_period(
            period_start_iso=week_date_iso, period_end_iso=week_date_iso
        )
        resolved = WeekResolver.resolve_weeks(runs)
        if week not in resolved:
            raise WeekNotResolvedError(f"No OK run for week {week}")
        run = resolved[week]

        raw = await self.reader.get_company_data(run_id=run.id, ticker=ticker)
        if raw is None:
            raise CompanyNotFoundError(f"{ticker} not in run {run.run_code}")

        # ADR-0002 pendiente: día uno devolvemos shape mínimo + el raw bajo
        # `raw_processed_stock` para no perder información.
        return {
            "ticker": str(ticker),
            "week_date": str(week),
            "run_code": run.run_code,
            "name": raw.get("Nom"),
            "country": raw.get("Country"),
            "exchange": raw.get("Exchange"),
            "currency": raw.get("StockCurrency"),
            "in_portfolio": await self._is_in_portfolio(run.id, ticker),
            "raw_processed_stock": raw,
        }

    async def _is_in_portfolio(self, run_id: int, ticker: TickerSymbol) -> bool:
        picks = await self.reader.get_picks_for_run(run_id=run_id)
        return any(p.ticker == ticker for p in picks)
