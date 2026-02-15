"""Pydantic models for paper trading."""

from datetime import datetime
from pydantic import BaseModel, Field


class OpenTradeRequest(BaseModel):
    market_id: str
    side: str  # YES or NO
    quantity: float
    at_timestamp: datetime | None = None
    fees: float = 0.0


class CloseTradeRequest(BaseModel):
    market_id: str
    side: str  # YES or NO
    quantity: float | None = None  # None = close all
    at_timestamp: datetime | None = None
    fees: float = 0.0


class PaperTrade(BaseModel):
    trade_id: str
    created_at_utc: datetime
    market_id: str
    side: str
    action: str  # OPEN or CLOSE
    quantity: float
    price: float
    snapshot_ts_utc: datetime | None = None
    fees: float = 0.0
    metadata: dict = Field(default_factory=dict)


class Position(BaseModel):
    market_id: str
    question: str = ""
    side: str
    net_quantity: float
    avg_entry_price: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    last_trade_date: str = ""
    closed: bool = False


class PortfolioSummary(BaseModel):
    total_equity: float = 0.0
    total_cost_basis: float = 0.0
    total_unrealized_pnl: float = 0.0
    total_realized_pnl: float = 0.0
    open_position_count: int = 0
    total_trades: int = 0
