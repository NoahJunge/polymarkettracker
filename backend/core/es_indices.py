"""Elasticsearch index mappings for all 6 indices."""

MARKETS_MAPPING = {
    "mappings": {
        "properties": {
            "market_id": {"type": "keyword"},
            "market_slug": {"type": "keyword"},
            "question": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 512}},
            },
            "outcomes": {"type": "keyword"},
            "active": {"type": "boolean"},
            "closed": {"type": "boolean"},
            "volumeNum": {"type": "double"},
            "liquidityNum": {"type": "double"},
            "source_tags": {"type": "keyword"},
            "polymarket_url": {"type": "keyword"},
            "end_date": {"type": "date"},
            "description": {"type": "text"},
            "resolution_source": {"type": "keyword"},
            "volume_24hr": {"type": "double"},
            "one_day_price_change": {"type": "double"},
            "first_seen_utc": {"type": "date"},
            "last_seen_utc": {"type": "date"},
        }
    },
}

SNAPSHOTS_WIDE_MAPPING = {
    "mappings": {
        "properties": {
            "timestamp_utc": {"type": "date"},
            "market_id": {"type": "keyword"},
            "question": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 512}},
            },
            "yes_price": {"type": "double"},
            "no_price": {"type": "double"},
            "yes_cents": {"type": "integer"},
            "no_cents": {"type": "integer"},
            "spread": {"type": "double"},
            "volumeNum": {"type": "double"},
            "liquidityNum": {"type": "double"},
            "active": {"type": "boolean"},
            "closed": {"type": "boolean"},
            "market_slug": {"type": "keyword"},
        }
    },
}

TRACKED_MARKETS_MAPPING = {
    "mappings": {
        "properties": {
            "market_id": {"type": "keyword"},
            "is_tracked": {"type": "boolean"},
            "stance": {"type": "keyword"},
            "pro_outcome": {"type": "keyword"},
            "priority": {"type": "integer"},
            "title_override": {"type": "text"},
            "notes": {"type": "text"},
            "created_at_utc": {"type": "date"},
            "updated_at_utc": {"type": "date"},
        }
    },
}

PAPER_TRADES_MAPPING = {
    "mappings": {
        "properties": {
            "trade_id": {"type": "keyword"},
            "created_at_utc": {"type": "date"},
            "market_id": {"type": "keyword"},
            "side": {"type": "keyword"},
            "action": {"type": "keyword"},
            "quantity": {"type": "double"},
            "price": {"type": "double"},
            "snapshot_ts_utc": {"type": "date"},
            "fees": {"type": "double"},
            "metadata": {"type": "object", "enabled": True},
        }
    },
}

SETTINGS_MAPPING = {
    "mappings": {
        "properties": {
            "collector_enabled": {"type": "boolean"},
            "collector_interval_minutes": {"type": "integer"},
            "cron_expression": {"type": "keyword"},
            "max_events_per_tag": {"type": "integer"},
            "tag_slugs": {"type": "keyword"},
            "trump_keywords": {"type": "keyword"},
            "require_binary_yes_no": {"type": "boolean"},
            "force_tracked_ids": {"type": "keyword"},
            "export_enabled": {"type": "boolean"},
            "export_frequency": {"type": "keyword"},
            "export_dir": {"type": "keyword"},
            "timezone": {"type": "keyword"},
            "updated_at_utc": {"type": "date"},
        }
    },
}

ALERTS_MAPPING = {
    "mappings": {
        "properties": {
            "alert_id": {"type": "keyword"},
            "market_id": {"type": "keyword"},
            "side": {"type": "keyword"},           # YES or NO
            "condition": {"type": "keyword"},       # ABOVE or BELOW
            "threshold": {"type": "double"},        # price threshold (0-1)
            "active": {"type": "boolean"},
            "triggered": {"type": "boolean"},
            "triggered_at_utc": {"type": "date"},
            "triggered_price": {"type": "double"},
            "created_at_utc": {"type": "date"},
            "note": {"type": "text"},
        }
    },
}

ALL_INDICES = {
    "markets": MARKETS_MAPPING,
    "snapshots_wide": SNAPSHOTS_WIDE_MAPPING,
    "tracked_markets": TRACKED_MARKETS_MAPPING,
    "paper_trades": PAPER_TRADES_MAPPING,
    "settings": SETTINGS_MAPPING,
    "alerts": ALERTS_MAPPING,
}
