"""Deterministic document ID generation for snapshot deduplication."""

from datetime import datetime, timezone


def generate_snapshot_doc_id(timestamp_utc: datetime, market_id: str) -> str:
    """Generate deterministic doc_id: '{ISO timestamp}|{market_id}'.

    Uses second-level precision. The same timestamp+market_id always produces
    the same doc_id, so ES will reject duplicates automatically.
    """
    if timestamp_utc.tzinfo is None:
        timestamp_utc = timestamp_utc.replace(tzinfo=timezone.utc)
    ts_str = timestamp_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"{ts_str}|{market_id}"


def parse_snapshot_doc_id(doc_id: str) -> tuple[datetime, str]:
    """Parse a snapshot doc_id back into (timestamp_utc, market_id)."""
    ts_str, market_id = doc_id.split("|", 1)
    timestamp = datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    return timestamp, market_id
