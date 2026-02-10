"""Pydantic models for application settings stored in ES."""

from datetime import datetime
from pydantic import BaseModel, Field


class Settings(BaseModel):
    collector_enabled: bool = True
    collector_interval_minutes: int = 60
    cron_expression: str | None = None
    max_events_per_tag: int = 300
    tag_slugs: list[str] = Field(default_factory=lambda: ["politics", "trump"])
    trump_keywords: list[str] = Field(
        default_factory=lambda: [
            "trump", "donald trump", "djt", "maga", "potus", "president trump"
        ]
    )
    require_binary_yes_no: bool = True
    force_tracked_ids: list[str] = Field(default_factory=list)
    export_enabled: bool = True
    export_frequency: str = "DAILY"
    export_dir: str = "/exports"
    timezone: str = "UTC"
    updated_at_utc: datetime | None = None


class SettingsUpdate(BaseModel):
    collector_enabled: bool | None = None
    collector_interval_minutes: int | None = None
    cron_expression: str | None = None
    max_events_per_tag: int | None = None
    tag_slugs: list[str] | None = None
    trump_keywords: list[str] | None = None
    require_binary_yes_no: bool | None = None
    force_tracked_ids: list[str] | None = None
    export_enabled: bool | None = None
    export_frequency: str | None = None
    export_dir: str | None = None
    timezone: str | None = None
