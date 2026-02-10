"""Export current ES data to seed_data/seed.xlsx for sharing via Git.

Usage (run from backend/ with ES running):
    python export_seed.py

Exports:
  - markets: all market metadata for tracked markets
  - snapshots_wide: all historical snapshots for tracked markets
  - tracked_markets: tracking configuration
"""

import asyncio
import logging
import os

import pandas as pd
from elasticsearch import AsyncElasticsearch

import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SEED_DIR = os.path.join(os.path.dirname(__file__), "seed_data")
SEED_FILE = os.path.join(SEED_DIR, "seed.xlsx")


async def scroll_all(es, index, query=None, size=1000):
    """Fetch all documents from an index using scroll API."""
    docs = []
    body = {"query": query or {"match_all": {}}, "size": size}
    resp = await es.search(index=index, body=body, scroll="2m")
    scroll_id = resp["_scroll_id"]
    hits = resp["hits"]["hits"]

    while hits:
        for hit in hits:
            doc = hit["_source"]
            doc["_doc_id"] = hit["_id"]
            docs.append(doc)
        resp = await es.scroll(scroll_id=scroll_id, scroll="2m")
        scroll_id = resp["_scroll_id"]
        hits = resp["hits"]["hits"]

    await es.clear_scroll(scroll_id=scroll_id)
    return docs


async def export_seed():
    """Export tracked markets data to seed Excel file."""
    es = AsyncElasticsearch(hosts=[config.ES_HOST], request_timeout=60)
    os.makedirs(SEED_DIR, exist_ok=True)

    try:
        # 1. Get tracked market IDs
        tracked_docs = await scroll_all(
            es, "tracked_markets", query={"term": {"is_tracked": True}}
        )
        tracked_ids = [d["market_id"] for d in tracked_docs]
        logger.info("Found %d tracked markets", len(tracked_ids))

        if not tracked_ids:
            logger.warning("No tracked markets found. Nothing to export.")
            return

        # 2. Export tracked_markets
        tracked_df = pd.DataFrame(tracked_docs)
        tracked_df = tracked_df.drop(columns=["_doc_id"], errors="ignore")
        logger.info("Tracked markets: %d rows", len(tracked_df))

        # 3. Export market metadata for tracked markets
        market_docs = await scroll_all(
            es, "markets", query={"terms": {"market_id": tracked_ids}}
        )
        markets_df = pd.DataFrame(market_docs)
        markets_df = markets_df.drop(columns=["_doc_id"], errors="ignore")
        # Convert list columns to pipe-delimited strings for Excel
        if "source_tags" in markets_df.columns:
            markets_df["source_tags"] = markets_df["source_tags"].apply(
                lambda x: "|".join(x) if isinstance(x, list) else str(x or "")
            )
        if "outcomes" in markets_df.columns:
            import json
            markets_df["outcomes"] = markets_df["outcomes"].apply(
                lambda x: json.dumps(x) if isinstance(x, list) else str(x or "[]")
            )
        logger.info("Markets: %d rows", len(markets_df))

        # 4. Export snapshots for tracked markets
        snapshot_docs = await scroll_all(
            es, "snapshots_wide", query={"terms": {"market_id": tracked_ids}}
        )
        snapshots_df = pd.DataFrame(snapshot_docs)
        snapshots_df = snapshots_df.drop(columns=["_doc_id"], errors="ignore")
        logger.info("Snapshots: %d rows", len(snapshots_df))

        # 5. Write to Excel
        with pd.ExcelWriter(SEED_FILE, engine="openpyxl") as writer:
            # Column order must match import_spreadsheet.py expectations
            snap_cols = [
                "timestamp_utc", "market_id", "question",
                "yes_price", "no_price", "yes_cents", "no_cents",
                "spread", "volumeNum", "liquidityNum", "active", "closed",
                "market_slug",
            ]
            snap_cols = [c for c in snap_cols if c in snapshots_df.columns]
            snapshots_df[snap_cols].to_excel(writer, index=False, sheet_name="snapshots_wide")

            market_cols = [
                "market_id", "market_slug", "question", "outcomes",
                "active", "closed", "volumeNum", "liquidityNum",
                "source_tags", "polymarket_url",
            ]
            market_cols = [c for c in market_cols if c in markets_df.columns]
            markets_df[market_cols].to_excel(writer, index=False, sheet_name="markets")

            track_cols = [
                "market_id", "is_tracked", "priority", "title_override", "notes",
            ]
            track_cols = [c for c in track_cols if c in tracked_df.columns]
            tracked_df[track_cols].to_excel(writer, index=False, sheet_name="tracked_markets")

        logger.info("Seed data exported to %s", SEED_FILE)
        size_mb = os.path.getsize(SEED_FILE) / (1024 * 1024)
        logger.info("File size: %.2f MB", size_mb)

    finally:
        await es.close()


if __name__ == "__main__":
    asyncio.run(export_seed())
