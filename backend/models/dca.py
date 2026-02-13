"""Pydantic models for DCA (Dollar-Cost Averaging) subscriptions."""

from datetime import datetime
from pydantic import BaseModel, Field


class CreateDCARequest(BaseModel):
    market_id: str
    side: str  # YES or NO
    quantity: float


class DCASubscription(BaseModel):
    dca_id: str
    market_id: str
    side: str
    quantity: float
    active: bool = True
    created_at_utc: datetime
    last_executed_date: str | None = None
    total_trades_placed: int = 0


class DCAAnalytics(BaseModel):
    dca_id: str
    market_id: str
    question: str = ""
    side: str
    quantity_per_day: float
    total_trades: int = 0
    total_shares: float = 0.0
    total_invested: float = 0.0
    avg_entry_price: float = 0.0
    current_price: float = 0.0
    current_value: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    first_trade_date: str = ""
    last_trade_date: str = ""
    trades: list[dict] = Field(default_factory=list)
