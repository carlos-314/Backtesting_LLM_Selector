import uuid
from datetime import date
from typing import Any

from pydantic import BaseModel


class HeatmapCell(BaseModel):
    ticker: str
    week_date: date
    in_universe: bool
    is_selected: bool


class TickerInfo(BaseModel):
    symbol: str
    name: str | None = None
    selection_count: int = 0


class HeatmapResponse(BaseModel):
    tickers: list[TickerInfo]
    weeks: list[date]
    cells: list[HeatmapCell]


class SignalSummary(BaseModel):
    week_date: date
    total_candidates: int
    total_selected: int


class SignalDetail(BaseModel):
    id: uuid.UUID
    ticker: str
    ticker_name: str | None = None
    week_date: date
    cagr_pot: float | None = None
    mediana_retorno_l5y: float | None = None
    pct_3m_alcista_5y: float | None = None
    mod1y_ev_ebit: float | None = None
    mod1y_ev_ebitda: float | None = None
    mod1y_p_fcf: float | None = None
    mod1y_per: float | None = None
    growth_rev_est_pend: str | None = None
    anal_rev_growth: float | None = None
    perfil_compounder: str | None = None
    estado_perf_vs_ev: str | None = None
    pq_barata: str | None = None
    orden: str | None = None
    status: str | None = None
    is_selected: bool = False


class DossierResponse(BaseModel):
    ticker: str
    week_date: date
    growth_profile: str | None = None
    margins_efficiency: str | None = None
    financial_health: str | None = None
    relative_valuation: str | None = None
    management_quality: str | None = None
    main_risks: str | None = None
    key_opportunities: str | None = None
    general_conclusion: str | None = None
    justification: str | None = None
    role_activity: str | None = None
    # Full signal data
    signal: SignalDetail | None = None
