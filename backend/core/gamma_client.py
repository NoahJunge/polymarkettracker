"""Polymarket Gamma API client with pagination and retry logic."""

import logging

import httpx

from utils.retry import retry_with_backoff

logger = logging.getLogger(__name__)

BASE_URL = "https://gamma-api.polymarket.com"


class GammaClient:
    def __init__(self, timeout: int = 30):
        self._client = httpx.AsyncClient(base_url=BASE_URL, timeout=timeout)

    async def close(self):
        await self._client.aclose()

    @retry_with_backoff(max_attempts=3, base_delay=1.0)
    async def _get(self, path: str, params: dict | None = None) -> dict | list:
        resp = await self._client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_events(
        self,
        tag_slug: str,
        active: bool = True,
        closed: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """Fetch a single page of events for a tag."""
        params = {
            "tag_slug": tag_slug,
            "active": str(active).lower(),
            "closed": str(closed).lower(),
            "limit": limit,
            "offset": offset,
        }
        result = await self._get("/events", params=params)
        return result if isinstance(result, list) else []

    async def get_all_events(
        self,
        tag_slug: str,
        max_events: int = 300,
        active: bool = True,
        closed: bool = False,
    ) -> list[dict]:
        """Paginate through all events for a tag, up to max_events."""
        all_events: list[dict] = []
        limit = 100
        offset = 0
        while offset < max_events:
            page_limit = min(limit, max_events - offset)
            page = await self.get_events(
                tag_slug=tag_slug,
                active=active,
                closed=closed,
                limit=page_limit,
                offset=offset,
            )
            if not page:
                break
            all_events.extend(page)
            if len(page) < page_limit:
                break
            offset += len(page)
        logger.info(
            "Fetched %d events for tag_slug=%s", len(all_events), tag_slug
        )
        return all_events

    @retry_with_backoff(max_attempts=3, base_delay=1.0)
    async def get_event_by_slug(self, event_slug: str) -> dict | None:
        """Fetch a single event by slug."""
        try:
            result = await self._get(f"/events/slug/{event_slug}")
            return result if isinstance(result, dict) else None
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    @retry_with_backoff(max_attempts=3, base_delay=1.0)
    async def get_market(self, market_id: str) -> dict | None:
        """Fetch a single market by ID for fresh prices."""
        try:
            result = await self._get(f"/markets/{market_id}")
            return result if isinstance(result, dict) else None
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
