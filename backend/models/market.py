"""Pydantic models for markets and snapshots."""

from datetime import datetime
from pydantic import BaseModel, Field


class Market(BaseModel):
    market_id: str
    market_slug: str = ""
    question: str = ""
    outcomes: list[str] = Field(default_factory=list)
    active: bool = True
    closed: bool = False
    volumeNum: float = 0.0
    liquidityNum: float = 0.0
    source_tags: list[str] = Field(default_factory=list)
    polymarket_url: str = ""
    end_date: datetime | None = None
    description: str = ""
    resolution_source: str = ""
    volume_24hr: float = 0.0
    one_day_price_change: float = 0.0
    first_seen_utc: datetime | None = None
    last_seen_utc: datetime | None = None


class SnapshotWide(BaseModel):
    timestamp_utc: datetime
    market_id: str
    question: str = ""
    yes_price: float = 0.0
    no_price: float = 0.0
    yes_cents: int = 0
    no_cents: int = 0
    spread: float = 0.0
    volumeNum: float = 0.0
    liquidityNum: float = 0.0
    active: bool = True
    closed: bool = False
    market_slug: str = ""


class MarketDetail(BaseModel):
    """Market with latest snapshot data merged."""
    market_id: str
    market_slug: str = ""
    question: str = ""
    outcomes: list[str] = Field(default_factory=list)
    active: bool = True
    closed: bool = False
    volumeNum: float = 0.0
    liquidityNum: float = 0.0
    source_tags: list[str] = Field(default_factory=list)
    polymarket_url: str = ""
    end_date: datetime | None = None
    description: str = ""
    resolution_source: str = ""
    volume_24hr: float = 0.0
    one_day_price_change: float = 0.0
    first_seen_utc: datetime | None = None
    last_seen_utc: datetime | None = None
    yes_price: float | None = None
    no_price: float | None = None
    is_tracked: bool = False
