"""Collector service — discovers Trump markets and collects snapshots."""

import logging
from datetime import datetime, timezone

from core.es_client import ESClient
from core.gamma_client import GammaClient
from services.settings_service import SettingsService
from utils.filters import is_trump_related, is_binary_yes_no, normalize_yes_no_prices
from utils.dedup import generate_snapshot_doc_id

logger = logging.getLogger(__name__)

MARKETS_INDEX = "markets"
SNAPSHOTS_INDEX = "snapshots_wide"
TRACKED_INDEX = "tracked_markets"


class CollectorService:
    def __init__(self, es: ESClient, gamma: GammaClient, settings_svc: SettingsService):
        self.es = es
        self.gamma = gamma
        self.settings_svc = settings_svc
        self.last_run_stats: dict | None = None
        self.last_run_utc: datetime | None = None
        self.is_running: bool = False

    async def run(self) -> dict:
        """Execute a full collection run. Returns stats dict."""
        if self.is_running:
            return {"error": "Collection already in progress"}

        self.is_running = True
        run_start = datetime.now(timezone.utc)
        stats = {
            "started_utc": run_start.isoformat(),
            "discovered": 0,
            "tracked": 0,
            "snapshots": 0,
            "errors": [],
        }

        try:
            settings = await self.settings_svc.get()

            # Step 1-4: Discover and filter markets
            discovered = await self._discover_markets(settings)
            stats["discovered"] = len(discovered)

            # Step 5: Upsert market metadata
            if discovered:
                await self._upsert_markets(discovered, run_start)

            # Step 6: Determine tracked set
            tracked_ids = await self._get_tracked_ids(settings)
            stats["tracked"] = len(tracked_ids)

            # Step 7-9: Collect snapshots for tracked markets
            if tracked_ids:
                snapshot_count, errors = await self._collect_snapshots(
                    tracked_ids, run_start
                )
                stats["snapshots"] = snapshot_count
                stats["errors"] = errors

        except Exception as e:
            logger.exception("Collection run failed")
            stats["errors"].append(str(e))
        finally:
            self.is_running = False
            run_end = datetime.now(timezone.utc)
            stats["finished_utc"] = run_end.isoformat()
            stats["duration_seconds"] = (run_end - run_start).total_seconds()
            self.last_run_stats = stats
            self.last_run_utc = run_end
            logger.info("Collection run completed: %s", stats)

        return stats

    async def _discover_markets(self, settings) -> list[dict]:
        """Discover markets from all configured tag_slugs."""
        all_markets: dict[str, dict] = {}  # keyed by market_id for dedup

        for tag_slug in settings.tag_slugs:
            try:
                events = await self.gamma.get_all_events(
                    tag_slug=tag_slug,
                    max_events=settings.max_events_per_tag,
                )
            except Exception as e:
                logger.error("Failed to fetch events for tag %s: %s", tag_slug, e)
                continue

            for event in events:
                event_end_date = event.get("endDate") or event.get("endDateIso") or None
                markets = event.get("markets", [])
                for market in markets:
                    mid = market.get("id")
                    if not mid:
                        continue

                    question = market.get("question", "") or market.get("title", "")
                    outcomes = market.get("outcomes", [])
                    if isinstance(outcomes, str):
                        import json
                        try:
                            outcomes = json.loads(outcomes)
                        except (json.JSONDecodeError, TypeError):
                            outcomes = []

                    outcome_prices = market.get("outcomePrices", [])
                    if isinstance(outcome_prices, str):
                        import json
                        try:
                            outcome_prices = json.loads(outcome_prices)
                        except (json.JSONDecodeError, TypeError):
                            outcome_prices = []

                    # Filter: trump tag → all; politics → keyword filter only
                    if tag_slug != "trump":
                        if not is_trump_related(question, settings.trump_keywords):
                            continue

                    # Binary filter
                    if settings.require_binary_yes_no:
                        if not is_binary_yes_no(outcomes, outcome_prices):
                            continue

                    # Extract yes/no prices from discovery data
                    yes_price, no_price = normalize_yes_no_prices(outcomes, outcome_prices)

                    # Build canonical market dict
                    slug = market.get("slug", "") or market.get("market_slug", "")
                    # End date: prefer market-level, fallback to event-level
                    end_date = market.get("endDate") or event_end_date
                    entry = {
                        "market_id": mid,
                        "market_slug": slug,
                        "question": question,
                        "outcomes": outcomes,
                        "active": market.get("active", True),
                        "closed": market.get("closed", False),
                        "volumeNum": float(market.get("volumeNum", 0) or 0),
                        "liquidityNum": float(market.get("liquidityNum", 0) or 0),
                        "polymarket_url": f"https://polymarket.com/event/{event.get('slug', '')}",
                        "end_date": end_date,
                        "description": market.get("description", "") or "",
                        "resolution_source": market.get("resolutionSource", "") or "",
                        "volume_24hr": float(market.get("volume24hr", 0) or 0),
                        "one_day_price_change": float(market.get("oneDayPriceChange", 0) or 0),
                        "yes_price": round(yes_price, 6) if yes_price else None,
                        "no_price": round(no_price, 6) if no_price else None,
                    }

                    if mid not in all_markets:
                        entry["source_tags"] = [tag_slug]
                        all_markets[mid] = entry
                    else:
                        # Merge source_tags
                        existing_tags = all_markets[mid].get("source_tags", [])
                        if tag_slug not in existing_tags:
                            existing_tags.append(tag_slug)
                        all_markets[mid]["source_tags"] = existing_tags

        logger.info("Discovered %d unique markets", len(all_markets))
        return list(all_markets.values())

    async def _upsert_markets(self, markets: list[dict], run_time: datetime):
        """Bulk upsert market metadata. Set first_seen_utc if new, always update last_seen_utc."""
        now_iso = run_time.isoformat()

        for m in markets:
            existing = await self.es.get(MARKETS_INDEX, m["market_id"])
            if existing:
                m["first_seen_utc"] = existing.get("first_seen_utc", now_iso)
            else:
                m["first_seen_utc"] = now_iso
            m["last_seen_utc"] = now_iso

        result = await self.es.bulk_upsert(MARKETS_INDEX, markets, id_field="market_id")
        logger.info("Upserted markets: %s", result)

    async def _get_tracked_ids(self, settings) -> list[str]:
        """Get all tracked market IDs: from tracked_markets index + force_tracked_ids."""
        tracked_ids = set()

        # From tracked_markets index
        result = await self.es.search(
            TRACKED_INDEX,
            query={"term": {"is_tracked": True}},
            size=10000,
        )
        for hit in result["hits"]["hits"]:
            tracked_ids.add(hit["_source"]["market_id"])

        # Force-tracked IDs from settings
        for mid in settings.force_tracked_ids:
            tracked_ids.add(mid)
            # Ensure they exist in tracked_markets
            existing = await self.es.get(TRACKED_INDEX, mid)
            if not existing:
                now = datetime.now(timezone.utc).isoformat()
                await self.es.index_doc(TRACKED_INDEX, mid, {
                    "market_id": mid,
                    "is_tracked": True,
                    "stance": None,
                    "pro_outcome": None,
                    "priority": None,
                    "title_override": None,
                    "notes": "Auto-added from force_tracked_ids",
                    "created_at_utc": now,
                    "updated_at_utc": now,
                })

        return list(tracked_ids)

    async def _collect_snapshots(
        self, tracked_ids: list[str], run_time: datetime
    ) -> tuple[int, list[str]]:
        """Fetch fresh prices for tracked markets and create snapshot docs."""
        snapshots = []
        errors = []
        ts_iso = run_time.isoformat()

        for mid in tracked_ids:
            try:
                market_data = await self.gamma.get_market(mid)
                if not market_data:
                    errors.append(f"Market {mid} not found")
                    continue

                outcomes = market_data.get("outcomes", [])
                if isinstance(outcomes, str):
                    import json
                    try:
                        outcomes = json.loads(outcomes)
                    except (json.JSONDecodeError, TypeError):
                        outcomes = []

                outcome_prices = market_data.get("outcomePrices", [])
                if isinstance(outcome_prices, str):
                    import json
                    try:
                        outcome_prices = json.loads(outcome_prices)
                    except (json.JSONDecodeError, TypeError):
                        outcome_prices = []

                if not outcomes or not outcome_prices or len(outcomes) < 2 or len(outcome_prices) < 2:
                    errors.append(f"Market {mid}: invalid outcomes/prices")
                    continue

                yes_price, no_price = normalize_yes_no_prices(outcomes, outcome_prices)
                doc_id = generate_snapshot_doc_id(run_time, mid)

                snapshot = {
                    "_id": doc_id,
                    "timestamp_utc": ts_iso,
                    "market_id": mid,
                    "question": market_data.get("question", ""),
                    "yes_price": round(yes_price, 6),
                    "no_price": round(no_price, 6),
                    "yes_cents": round(yes_price * 100),
                    "no_cents": round(no_price * 100),
                    "spread": round(abs(yes_price - no_price), 6),
                    "volumeNum": float(market_data.get("volumeNum", 0) or 0),
                    "liquidityNum": float(market_data.get("liquidityNum", 0) or 0),
                    "active": market_data.get("active", True),
                    "closed": market_data.get("closed", False),
                    "market_slug": market_data.get("slug", ""),
                }
                snapshots.append(snapshot)

            except Exception as e:
                logger.error("Error collecting snapshot for %s: %s", mid, e)
                errors.append(f"Market {mid}: {e}")

        if snapshots:
            result = await self.es.bulk_index(SNAPSHOTS_INDEX, snapshots)
            logger.info("Indexed %d snapshots: %s", len(snapshots), result)

        return len(snapshots), errors
