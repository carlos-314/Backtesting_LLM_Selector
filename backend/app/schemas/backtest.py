import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


class BacktestCreate(BaseModel):
    name: str | None = None
    start_date: date
    end_date: date
    initial_capital: float = 100000
    commission_pct: float = 0.001
    slippage_bps: float = 5
    rebalance_mode: str = "composition"
    deduplicate: bool = True
    exclude_llm_errors: bool = True
    use_equal_weight_bench: bool = True
    use_random_bench: bool = True
    random_simulations: int = 1000
    external_index_symbol: str | None = None


class BacktestRunResponse(BaseModel):
    id: uuid.UUID
    name: str | None = None
    status: str
    start_date: date
    end_date: date
    initial_capital: float
    commission_pct: float
    slippage_bps: float
    rebalance_mode: str
    use_equal_weight_bench: bool
    use_random_bench: bool
    random_simulations: int
    external_index_symbol: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class MetricsResponse(BaseModel):
    source: str
    total_return: float | None = None
    cagr: float | None = None
    volatility: float | None = None
    sharpe_ratio: float | None = None
    max_drawdown: float | None = None
    sortino_ratio: float | None = None
    calmar_ratio: float | None = None
    win_rate: float | None = None
    turnover: float | None = None
    pct_random_beaten: float | None = None
    equity_curve: list[dict[str, Any]] | None = None

    model_config = {"from_attributes": True}


class BacktestDetailResponse(BaseModel):
    run: BacktestRunResponse
    metrics: list[MetricsResponse]


class TradeRecord(BaseModel):
    date: date
    ticker: str
    side: str
    shares: float
    price: float
    cost: float
    notional: float


class CompareResponse(BaseModel):
    runs: list[BacktestRunResponse]
    metrics: list[list[MetricsResponse]]
