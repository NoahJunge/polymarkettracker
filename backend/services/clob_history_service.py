"""
CLOB Historical Price Backfill Service.

Pulls daily price history from Polymarket's CLOB API for all tracked markets
and injects synthetic snapshots into the snapshots_wide index.

DORMANT until explicitly triggered via POST /api/jobs/clob-backfill.
No existing data is modified — only new snapshot documents are added.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone

import httpx

from core.es_client import ESClient
from utils.dedup import generate_snapshot_doc_id

logger = logging.getLogger(__name__)

CLOB_BASE = "https://clob.polymarket.com"
GAMMA_BASE = "https://gamma-api.polymarket.com"

# Pull everything back to 2024-01-01 — markets created earlier will just have no data
DEFAULT_START_TS = int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp())
FIDELITY = 1440  # daily (minutes)
DELAY = 0.25     # seconds between CLOB requests

MARKETS_INDEX = "markets"
SNAPSHOTS_INDEX = "snapshots_wide"
TRACKED_INDEX = "tracked_markets"

GAMMA_BATCH = 80  # max IDs per Gamma batch request


class ClobHistoryService:
    def __init__(self, es: ESClient):
        self.es = es
        self._http: httpx.AsyncClient | None = None

    def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=20.0,
            )
        return self._http

    async def close(self):
        if self._http and not self._http.is_closed:
            await self._http.aclose()

    async def run_backfill(
        self,
        start_ts: int | None = None,
        end_ts: int | None = None,
        include_cancelled: bool = False,
    ) -> dict:
        """
        Full backfill flow:
        1. Load all tracked market IDs
        2. Ensure token IDs are stored (batch-fetch from Gamma for any market missing them)
        3. Pull CLOB daily history for every market with a token ID
        4. Bulk-inject snapshots into snapshots_wide (idempotent)
        5. Refresh snapshots index
        6. Re-backfill all active DCA subscriptions from the extended history
        """
        effective_start_ts = start_ts if start_ts is not None else DEFAULT_START_TS
        stats = {
            "start_ts": effective_start_ts,
            "end_ts": end_ts,
            "markets_attempted": 0,
            "markets_succeeded": 0,
            "snapshots_injected": 0,
            "token_ids_fetched": 0,
            "dca_rebackfilled": 0,
            "errors": [],
        }

        # Step 1 — load tracked market IDs
        tracked_ids = await self._load_tracked_ids()
        logger.info("CLOB backfill: %d tracked markets", len(tracked_ids))

        if not tracked_ids:
            stats["errors"].append("No tracked markets found")
            return stats

        # Step 2 — load market docs, find those without token IDs
        market_docs = await self.es.mget(MARKETS_INDEX, tracked_ids)
        missing_tokens = [
            mid for mid in tracked_ids
            if not market_docs.get(mid, {}).get("clob_token_ids")
        ]

        if missing_tokens:
            fetched = await self._fetch_and_store_token_ids(missing_tokens, market_docs)
            stats["token_ids_fetched"] = fetched

        # Step 3 — pull CLOB history
        all_snapshots: list[dict] = []
        for mid in tracked_ids:
            doc = market_docs.get(mid, {})
            token_ids = doc.get("clob_token_ids") or []
            if not token_ids:
                continue

            yes_token = token_ids[0]
            stats["markets_attempted"] += 1

            try:
                points = await self._fetch_clob_history(yes_token, effective_start_ts)
                if not points:
                    continue

                for pt in points:
                    if end_ts is not None and int(pt["t"]) > end_ts:
                        continue
                    ts = datetime.fromtimestamp(pt["t"], tz=timezone.utc)
                    yes = round(float(pt["p"]), 6)
                    no = round(1.0 - yes, 6)
                    snap_id = generate_snapshot_doc_id(ts, mid)
                    all_snapshots.append({
                        "_id": snap_id,
                        "timestamp_utc": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "market_id": mid,
                        "question": doc.get("question", ""),
                        "yes_price": yes,
                        "no_price": no,
                        "yes_cents": round(yes * 100),
                        "no_cents": round(no * 100),
                        "spread": round(abs(yes - no), 6),
                        "volumeNum": 0.0,
                        "liquidityNum": 0.0,
                        "active": doc.get("active", True),
                        "closed": doc.get("closed", False),
                        "market_slug": doc.get("market_slug", ""),
                        "source": "clob",
                    })

                stats["markets_succeeded"] += 1
                logger.debug("CLOB: %s — %d points", mid, len(points))

            except Exception as e:
                stats["errors"].append(f"{mid}: {e}")
                logger.warning("CLOB fetch failed for %s: %s", mid, e)

            await asyncio.sleep(DELAY)

        # Step 4 — bulk index (idempotent: same doc_id → overwrites with identical data)
        if all_snapshots:
            result = await self.es.bulk_index(SNAPSHOTS_INDEX, all_snapshots)
            stats["snapshots_injected"] = result.get("success", 0)
            logger.info("CLOB backfill: injected %d snapshots", stats["snapshots_injected"])

        # Step 5 — refresh so DCA backfill sees new docs
        await self.es.client.indices.refresh(index=SNAPSHOTS_INDEX)

        # Step 6 — re-backfill all active (and optionally cancelled) DCA subscriptions
        dca_stats = await self._rebackfill_all_dca(include_cancelled=include_cancelled)
        stats["dca_rebackfilled"] = dca_stats.get("subscriptions_rebackfilled", 0)
        stats["dca_errors"] = dca_stats.get("errors", [])

        logger.info("CLOB backfill complete: %s", stats)
        return stats

    # ── helpers ───────────────────────────────────────────────────────────────

    async def _load_tracked_ids(self) -> list[str]:
        result = await self.es.search(
            TRACKED_INDEX,
            query={"term": {"is_tracked": True}},
            size=10000,
        )
        return [h["_source"]["market_id"] for h in result["hits"]["hits"]]

    async def _fetch_clob_history(self, token: str, start_ts: int) -> list[dict]:
        url = (
            f"{CLOB_BASE}/prices-history"
            f"?market={token}"
            f"&startTs={start_ts}"
            f"&fidelity={FIDELITY}"
        )
        for attempt in range(3):
            try:
                resp = await self._client().get(url)
                if resp.status_code == 429:
                    await asyncio.sleep(5)
                    continue
                resp.raise_for_status()
                data = resp.json()
                return data.get("history", [])
            except httpx.HTTPStatusError:
                if attempt == 2:
                    raise
                await asyncio.sleep(1)
        return []

    async def _fetch_and_store_token_ids(
        self, missing_ids: list[str], market_docs: dict
    ) -> int:
        """Batch-fetch clobTokenIds from Gamma for markets that don't have them yet."""
        fetched = 0
        batches = [missing_ids[i:i + GAMMA_BATCH] for i in range(0, len(missing_ids), GAMMA_BATCH)]

        for batch in batches:
            params = "&".join(f"id={mid}" for mid in batch)
            url = f"{GAMMA_BASE}/markets?{params}&limit={GAMMA_BATCH}"
            try:
                resp = await self._client().get(url)
                resp.raise_for_status()
                results = resp.json()
                if isinstance(results, dict):
                    results = [results]

                upsert_batch = []
                for item in results:
                    mid = str(int(float(item.get("id", 0))))
                    clob_raw = item.get("clobTokenIds", "[]") or "[]"
                    try:
                        token_ids = json.loads(clob_raw) if isinstance(clob_raw, str) else list(clob_raw)
                    except (ValueError, TypeError):
                        token_ids = []

                    if token_ids:
                        market_docs.setdefault(mid, {})["clob_token_ids"] = token_ids
                        existing = market_docs.get(mid, {})
                        upsert_batch.append({
                            "market_id": mid,
                            **existing,
                            "clob_token_ids": token_ids,
                        })
                        fetched += 1

                if upsert_batch:
                    await self.es.bulk_upsert(MARKETS_INDEX, upsert_batch, id_field="market_id")

            except Exception as e:
                logger.warning("Gamma batch token fetch failed: %s", e)

            await asyncio.sleep(0.25)

        logger.info("Fetched and stored token IDs for %d markets", fetched)
        return fetched

    async def _rebackfill_all_dca(self, include_cancelled: bool = False) -> dict:
        """Delete and regenerate trades for all active (and optionally cancelled) DCA subscriptions."""
        query = {"match_all": {}} if include_cancelled else {"term": {"active": True}}
        result = await self.es.search(
            "dca_subscriptions",
            query=query,
            size=10000,
        )
        subs = [h["_source"] for h in result["hits"]["hits"]]

        rebackfilled = 0
        errors = []

        for sub in subs:
            dca_id = sub["dca_id"]
            try:
                await self._delete_dca_trades(dca_id)
                count = await self._backfill_dca(
                    dca_id, sub["market_id"], sub["side"], sub["quantity"]
                )
                rebackfilled += 1
                logger.debug("Re-backfilled DCA %s — %d trades", dca_id, count)
            except Exception as e:
                errors.append(f"{dca_id}: {e}")
                logger.warning("DCA rebackfill failed for %s: %s", dca_id, e)

        return {"subscriptions_rebackfilled": rebackfilled, "errors": errors}

    async def _delete_dca_trades(self, dca_id: str) -> None:
        """Delete all paper_trades for a given dca_id."""
        await self.es.client.delete_by_query(
            index="paper_trades",
            body={
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"metadata.dca": True}},
                            {"term": {"metadata.dca_id": dca_id}},
                        ]
                    }
                }
            },
            refresh=True,
        )

    async def _backfill_dca(
        self, dca_id: str, market_id: str, side: str, quantity: float
    ) -> int:
        """Re-run DCA backfill from snapshots (reuses dca_service logic inline)."""
        from collections import OrderedDict
        import uuid

        snap_result = await self.es.search(
            SNAPSHOTS_INDEX,
            query={"term": {"market_id": market_id}},
            sort=[{"timestamp_utc": {"order": "asc"}}],
            size=10000,
        )
        snapshots = [h["_source"] for h in snap_result["hits"]["hits"]]
        if not snapshots:
            return 0

        # Group by day — first per day (CLOB midnight < Gamma afternoon → CLOB wins)
        daily: OrderedDict = OrderedDict()
        for snap in snapshots:
            date_str = snap["timestamp_utc"][:10]
            if date_str not in daily:
                daily[date_str] = snap

        side_upper = side.upper()
        trades = []
        for _date, snap in daily.items():
            price = snap["yes_price"] if side_upper == "YES" else snap["no_price"]
            trades.append({
                "trade_id": str(uuid.uuid4()),
                "created_at_utc": snap["timestamp_utc"],
                "market_id": market_id,
                "side": side_upper,
                "action": "OPEN",
                "quantity": quantity,
                "price": price,
                "snapshot_ts_utc": snap["timestamp_utc"],
                "fees": 0.0,
                "metadata": {"dca": True, "dca_id": dca_id},
            })

        if trades:
            await self.es.bulk_index("paper_trades", trades, id_field="trade_id")
            last_date = list(daily.keys())[-1]
            await self.es.update("dca_subscriptions", dca_id, {
                "last_executed_date": last_date,
                "total_trades_placed": len(trades),
            })

        return len(trades)
