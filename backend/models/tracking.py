"""Pydantic models for tracked market configuration."""

from datetime import datetime
from pydantic import BaseModel


class TrackedMarketUpdate(BaseModel):
    is_tracked: bool = True
    stance: str | None = None       # pro | anti | neutral
    pro_outcome: str | None = None  # Yes | No
    priority: int | None = None
    title_override: str | None = None
    notes: str | None = None


class TrackedMarket(BaseModel):
    market_id: str
    is_tracked: bool = True
    stance: str | None = None
    pro_outcome: str | None = None
    priority: int | None = None
    title_override: str | None = None
    notes: str | None = None
    created_at_utc: datetime | None = None
    updated_at_utc: datetime | None = None
