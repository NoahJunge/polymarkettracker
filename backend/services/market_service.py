"""Market service — query markets and snapshots from ES."""

import logging
from datetime import datetime, timezone, timedelta

from core.es_client import ESClient

logger = logging.getLogger(__name__)

MARKETS_INDEX = "markets"
SNAPSHOTS_INDEX = "snapshots_wide"
TRACKED_INDEX = "tracked_markets"


class MarketService:
    def __init__(self, es: ESClient):
        self.es = es

    async def list_markets(
        self,
        tracked: bool | None = None,
        search: str | None = None,
        category: str | None = None,
        sort: str = "volumeNum",
        order: str = "desc",
        size: int = 100,
        from_: int = 0,
    ) -> dict:
        """List markets with optional tracking filter, search, category, and sort."""
        must_clauses = []

        if tracked is not None:
            # Get tracked market IDs
            tracked_result = await self.es.search(
                TRACKED_INDEX,
                query={"term": {"is_tracked": True}},
                size=10000,
            )
            tracked_ids = [
                h["_source"]["market_id"] for h in tracked_result["hits"]["hits"]
            ]

            if tracked:
                if not tracked_ids:
                    return {"markets": [], "total": 0}
                must_clauses.append({"terms": {"market_id": tracked_ids}})
            else:
                if tracked_ids:
                    must_clauses.append(
                        {"bool": {"must_not": {"terms": {"market_id": tracked_ids}}}}
                    )

        if search:
            must_clauses.append(
                {"match": {"question": {"query": search, "fuzziness": "AUTO"}}}
            )

        if category:
            must_clauses.append({"term": {"source_tags": category}})

        query = {"bool": {"must": must_clauses}} if must_clauses else {"match_all": {}}

        sort_field = {
            "volume": "volumeNum",
            "liquidity": "liquidityNum",
            "updated": "last_seen_utc",
        }.get(sort, sort)

        result = await self.es.search(
            MARKETS_INDEX,
            query=query,
            sort=[{sort_field: {"order": order}}],
            size=size,
            from_=from_,
        )

        markets = []
        for hit in result["hits"]["hits"]:
            m = hit["_source"]
            m["_id"] = hit["_id"]
            markets.append(m)

        # Enrich with latest snapshot prices and tracking status
        if markets:
            await self._enrich_with_prices(markets)
            await self._enrich_with_tracking(markets)

        total = result["hits"]["total"]["value"]
        return {"markets": markets, "total": total}

    async def get_market(self, market_id: str) -> dict | None:
        """Get a single market with latest price and tracking status."""
        market = await self.es.get(MARKETS_INDEX, market_id)
        if not market:
            return None
        market["market_id"] = market_id
        await self._enrich_with_prices([market])
        await self._enrich_with_tracking([market])
        return market

    async def get_snapshots(
        self,
        market_id: str,
        limit: int = 500,
        from_ts: str | None = None,
        to_ts: str | None = None,
        sort: str = "desc",
    ) -> list[dict]:
        """Get snapshots for a market, optionally filtered by time range."""
        must_clauses = [{"term": {"market_id": market_id}}]

        if from_ts or to_ts:
            range_q: dict = {}
            if from_ts:
                range_q["gte"] = from_ts
            if to_ts:
                range_q["lte"] = to_ts
            must_clauses.append({"range": {"timestamp_utc": range_q}})

        result = await self.es.search(
            SNAPSHOTS_INDEX,
            query={"bool": {"must": must_clauses}},
            sort=[{"timestamp_utc": {"order": sort}}],
            size=limit,
        )

        return [hit["_source"] for hit in result["hits"]["hits"]]

    async def get_new_bets(
        self,
        search: str | None = None,
        category: str | None = None,
        sort: str = "volumeNum",
        order: str = "desc",
        size: int = 100,
        from_: int = 0,
    ) -> dict:
        """Get discovered markets that are NOT tracked."""
        # Get all tracked market IDs
        tracked_result = await self.es.search(
            TRACKED_INDEX,
            query={"term": {"is_tracked": True}},
            size=10000,
        )
        tracked_ids = [
            h["_source"]["market_id"] for h in tracked_result["hits"]["hits"]
        ]

        # Build query: not tracked + optional search + optional category
        must_clauses: list[dict] = []
        must_not_clauses: list[dict] = []

        if tracked_ids:
            must_not_clauses.append({"terms": {"market_id": tracked_ids}})

        if search:
            must_clauses.append(
                {"match": {"question": {"query": search, "fuzziness": "AUTO"}}}
            )

        if category:
            must_clauses.append({"term": {"source_tags": category}})

        query: dict
        if must_clauses or must_not_clauses:
            query = {"bool": {}}
            if must_clauses:
                query["bool"]["must"] = must_clauses
            if must_not_clauses:
                query["bool"]["must_not"] = must_not_clauses
        else:
            query = {"match_all": {}}

        sort_field = {
            "volume": "volumeNum",
            "liquidity": "liquidityNum",
            "updated": "last_seen_utc",
        }.get(sort, sort)

        result = await self.es.search(
            MARKETS_INDEX,
            query=query,
            sort=[{sort_field: {"order": order}}],
            size=size,
            from_=from_,
        )

        markets = [hit["_source"] for hit in result["hits"]["hits"]]
        total = result["hits"]["total"]["value"]
        return {"markets": markets, "total": total}

    async def get_categories(self) -> list[str]:
        """Get all unique source_tags (categories) across markets."""
        result = await self.es.client.search(
            index=MARKETS_INDEX,
            body={
                "size": 0,
                "aggs": {
                    "categories": {
                        "terms": {"field": "source_tags", "size": 50}
                    }
                },
            },
        )
        buckets = result["aggregations"]["categories"]["buckets"]
        return [b["key"] for b in buckets]

    async def get_dashboard_summary(self) -> dict:
        """Get summary stats for the dashboard: biggest movers, closing soon, totals."""
        # Get all tracked market IDs
        tracked_result = await self.es.search(
            TRACKED_INDEX,
            query={"term": {"is_tracked": True}},
            size=10000,
        )
        tracked_ids = [
            h["_source"]["market_id"] for h in tracked_result["hits"]["hits"]
        ]

        if not tracked_ids:
            return {
                "total_tracked": 0,
                "total_discovered": 0,
                "biggest_movers": [],
                "closing_soon": [],
            }

        # Get tracked markets sorted by absolute price change
        tracked_markets_result = await self.es.search(
            MARKETS_INDEX,
            query={"terms": {"market_id": tracked_ids}},
            sort=[{"one_day_price_change": {"order": "desc"}}],
            size=1000,
        )
        tracked_markets = [h["_source"] for h in tracked_markets_result["hits"]["hits"]]

        # Biggest movers: top 5 by absolute one_day_price_change
        movers = sorted(
            tracked_markets,
            key=lambda m: abs(m.get("one_day_price_change", 0) or 0),
            reverse=True,
        )[:5]

        # Closing soon: tracked markets with end_date in the next 30 days
        now = datetime.now(timezone.utc)
        thirty_days = now + timedelta(days=30)
        closing_soon = []
        for m in tracked_markets:
            ed = m.get("end_date")
            if not ed:
                continue
            try:
                if isinstance(ed, str):
                    end_dt = datetime.fromisoformat(ed.replace("Z", "+00:00"))
                else:
                    end_dt = ed
                if now < end_dt <= thirty_days:
                    m["days_until_close"] = (end_dt - now).days
                    closing_soon.append(m)
            except (ValueError, TypeError):
                continue
        closing_soon.sort(key=lambda m: m.get("days_until_close", 999))
        closing_soon = closing_soon[:5]

        # Total discovered
        total_discovered = await self.es.count(MARKETS_INDEX)

        return {
            "total_tracked": len(tracked_ids),
            "total_discovered": total_discovered,
            "biggest_movers": movers,
            "closing_soon": closing_soon,
        }

    async def _enrich_with_prices(self, markets: list[dict]):
        """Add latest yes_price/no_price from snapshots."""
        for m in markets:
            mid = m.get("market_id")
            if not mid:
                continue
            result = await self.es.search(
                SNAPSHOTS_INDEX,
                query={"term": {"market_id": mid}},
                sort=[{"timestamp_utc": {"order": "desc"}}],
                size=1,
            )
            if result["hits"]["hits"]:
                snap = result["hits"]["hits"][0]["_source"]
                m["yes_price"] = snap.get("yes_price")
                m["no_price"] = snap.get("no_price")
                m["latest_snapshot_utc"] = snap.get("timestamp_utc")

    async def _enrich_with_tracking(self, markets: list[dict]):
        """Add is_tracked flag from tracked_markets index."""
        for m in markets:
            mid = m.get("market_id")
            if not mid:
                continue
            tracked = await self.es.get(TRACKED_INDEX, mid)
            m["is_tracked"] = bool(tracked and tracked.get("is_tracked"))
