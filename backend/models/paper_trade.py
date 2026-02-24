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


class EquityCurvePoint(BaseModel):
    date: str
    total_pnl: float  # unrealized + realized combined
    unrealized_pnl: float
    realized_pnl: float
    cumulative_invested: float
    portfolio_value: float  # current market value of open positions
    total_open_trades: int
    total_close_trades: int


class PortfolioStats(BaseModel):
    win_rate: float | None = None
    profit_factor: float | None = None
    sharpe_ratio: float | None = None
    max_drawdown: float | None = None
    avg_win: float | None = None
    avg_loss: float | None = None
    total_wins: int = 0
    total_losses: int = 0
    regression_slope: float | None = None
    regression_r_squared: float | None = None
    regression_p_value: float | None = None
    trend_direction: str | None = None  # "up", "down", or "none"
    trend_significant: bool = False


class EquityCurveResponse(BaseModel):
    curve: list[EquityCurvePoint]
    stats: PortfolioStats
