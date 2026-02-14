"""Elasticsearch client wrapper with bulk operations and index management."""

import logging
from typing import Any

from elasticsearch import AsyncElasticsearch, NotFoundError
from elasticsearch.helpers import async_bulk

logger = logging.getLogger(__name__)


class ESClient:
    def __init__(self, hosts: list[str], timeout: int = 30):
        self.client = AsyncElasticsearch(hosts=hosts, request_timeout=timeout)

    async def close(self):
        await self.client.close()

    async def health(self) -> dict:
        return await self.client.cluster.health()

    async def ensure_index(self, name: str, body: dict) -> bool:
        """Create index if it doesn't exist. If it exists, update mappings with any new fields."""
        if await self.client.indices.exists(index=name):
            # Update mappings to add any new fields (ES allows adding, not modifying)
            if "mappings" in body and "properties" in body["mappings"]:
                try:
                    await self.client.indices.put_mapping(
                        index=name, properties=body["mappings"]["properties"]
                    )
                    logger.info("Updated mappings for index: %s", name)
                except Exception as e:
                    logger.warning("Could not update mappings for %s: %s", name, e)
            return False
        await self.client.indices.create(index=name, body=body)
        logger.info("Created index: %s", name)
        return True

    async def index_doc(self, index: str, doc_id: str, body: dict) -> dict:
        return await self.client.index(index=index, id=doc_id, document=body)

    async def get(self, index: str, doc_id: str) -> dict | None:
        try:
            result = await self.client.get(index=index, id=doc_id)
            return result["_source"]
        except NotFoundError:
            return None

    async def update(self, index: str, doc_id: str, body: dict) -> dict:
        return await self.client.update(index=index, id=doc_id, doc=body)

    async def delete(self, index: str, doc_id: str) -> bool:
        try:
            await self.client.delete(index=index, id=doc_id)
            return True
        except NotFoundError:
            return False

    async def search(
        self,
        index: str,
        query: dict | None = None,
        sort: list | None = None,
        size: int = 100,
        from_: int = 0,
        collapse: str | None = None,
    ) -> dict:
        body: dict[str, Any] = {"size": size, "from": from_}
        if query:
            body["query"] = query
        if sort:
            body["sort"] = sort
        if collapse:
            body["collapse"] = {"field": collapse}
        return await self.client.search(index=index, body=body)

    async def count(self, index: str, query: dict | None = None) -> int:
        body = {"query": query} if query else {}
        result = await self.client.count(index=index, body=body)
        return result["count"]

    async def mget(self, index: str, ids: list[str]) -> dict[str, dict]:
        """Fetch multiple documents by ID. Returns {doc_id: source} for found docs."""
        if not ids:
            return {}
        result = await self.client.mget(index=index, ids=ids)
        return {
            doc["_id"]: doc["_source"]
            for doc in result["docs"]
            if doc.get("found")
        }

    async def bulk_index(
        self, index: str, documents: list[dict], id_field: str | None = None
    ) -> dict:
        """Bulk index documents. If id_field is set, use that field as the ES doc _id."""
        actions = []
        for doc in documents:
            action = {"_index": index, "_source": doc}
            if id_field and id_field in doc:
                action["_id"] = doc[id_field]
            elif "_id" in doc:
                action["_id"] = doc.pop("_id")
            actions.append(action)

        success, errors = await async_bulk(
            self.client,
            actions,
            chunk_size=500,
            raise_on_error=False,
        )
        if errors:
            logger.warning("Bulk index had %d errors", len(errors))
        return {"success": success, "errors": len(errors) if errors else 0}

    async def bulk_upsert(
        self, index: str, documents: list[dict], id_field: str
    ) -> dict:
        """Bulk upsert: index documents using id_field as doc _id (overwrites if exists)."""
        actions = []
        for doc in documents:
            doc_id = doc.get(id_field)
            if not doc_id:
                continue
            actions.append({"_index": index, "_id": doc_id, "_source": doc})

        success, errors = await async_bulk(
            self.client,
            actions,
            chunk_size=500,
            raise_on_error=False,
        )
        if errors:
            logger.warning("Bulk upsert had %d errors", len(errors))
        return {"success": success, "errors": len(errors) if errors else 0}
