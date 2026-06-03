import uuid
from datetime import date, datetime

from pydantic import BaseModel


class TickerResponse(BaseModel):
    id: uuid.UUID
    symbol: str
    name: str | None = None
    exchange: str | None = None
    currency: str
    sector: str | None = None
    last_price_update: datetime | None = None

    model_config = {"from_attributes": True}


class PriceRecord(BaseModel):
    date: date
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    adj_close: float | None = None
    volume: int | None = None
