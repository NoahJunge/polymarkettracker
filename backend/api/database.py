"""Database browsing and Excel export endpoints."""

import io
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Query
from fastapi.responses import StreamingResponse

import pandas as pd

logger = logging.getLogger(__name__)

router = APIRouter()

SNAPSHOTS_INDEX = "snapshots_wide"
TRACKED_INDEX = "tracked_markets"
MARKETS_INDEX = "markets"


@router.get("/database/markets")
async def list_tracked_markets_for_db(
    request: Request,
    search: str | None = None,
):
    """List tracked markets for the database page dropdown/search."""
    es = request.app.state.es

    # Get tracked IDs
    tracked_result = await es.search(
        TRACKED_INDEX,
        query={"term": {"is_tracked": True}},
        size=10000,
    )
    tracked_ids = [h["_source"]["market_id"] for h in tracked_result["hits"]["hits"]]

    if not tracked_ids:
        return {"markets": [], "total": 0}

    must_clauses = [{"terms": {"market_id": tracked_ids}}]
    if search:
        must_clauses.append(
            {"match": {"question": {"query": search, "fuzziness": "AUTO"}}}
        )

    result = await es.search(
        MARKETS_INDEX,
        query={"bool": {"must": must_clauses}},
        sort=[{"volumeNum": {"order": "desc"}}],
        size=500,
    )

    markets = []
    for hit in result["hits"]["hits"]:
        m = hit["_source"]
        markets.append({
            "market_id": m.get("market_id"),
            "question": m.get("question", ""),
            "active": m.get("active", True),
            "closed": m.get("closed", False),
        })

    return {"markets": markets, "total": len(markets)}


@router.get("/database/snapshots")
async def get_database_snapshots(
    request: Request,
    market_id: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    size: int = Query(50, ge=1, le=1000),
    from_: int = Query(0, ge=0, alias="from"),
):
    """Browse snapshots with optional market and date filters."""
    es = request.app.state.es

    must_clauses = []

    if market_id:
        must_clauses.append({"term": {"market_id": market_id}})
    else:
        # Only show tracked markets
        tracked_result = await es.search(
            TRACKED_INDEX,
            query={"term": {"is_tracked": True}},
            size=10000,
        )
        tracked_ids = [h["_source"]["market_id"] for h in tracked_result["hits"]["hits"]]
        if tracked_ids:
            must_clauses.append({"terms": {"market_id": tracked_ids}})

    if from_date or to_date:
        range_q = {}
        if from_date:
            range_q["gte"] = from_date
        if to_date:
            range_q["lte"] = to_date
        must_clauses.append({"range": {"timestamp_utc": range_q}})

    query = {"bool": {"must": must_clauses}} if must_clauses else {"match_all": {}}

    result = await es.search(
        SNAPSHOTS_INDEX,
        query=query,
        sort=[{"timestamp_utc": {"order": "desc"}}],
        size=size,
        from_=from_,
    )

    snapshots = [hit["_source"] for hit in result["hits"]["hits"]]
    total = result["hits"]["total"]["value"]

    return {"snapshots": snapshots, "total": total}


@router.get("/database/export")
async def export_database_xlsx(
    request: Request,
    market_id: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
):
    """Export filtered snapshots as an Excel file download."""
    es = request.app.state.es

    must_clauses = []

    if market_id:
        must_clauses.append({"term": {"market_id": market_id}})
    else:
        tracked_result = await es.search(
            TRACKED_INDEX,
            query={"term": {"is_tracked": True}},
            size=10000,
        )
        tracked_ids = [h["_source"]["market_id"] for h in tracked_result["hits"]["hits"]]
        if tracked_ids:
            must_clauses.append({"terms": {"market_id": tracked_ids}})

    if from_date or to_date:
        range_q = {}
        if from_date:
            range_q["gte"] = from_date
        if to_date:
            range_q["lte"] = to_date
        must_clauses.append({"range": {"timestamp_utc": range_q}})

    query = {"bool": {"must": must_clauses}} if must_clauses else {"match_all": {}}

    # Fetch all matching snapshots (up to 10k)
    result = await es.search(
        SNAPSHOTS_INDEX,
        query=query,
        sort=[{"timestamp_utc": {"order": "desc"}}],
        size=10000,
    )

    rows = [hit["_source"] for hit in result["hits"]["hits"]]

    if not rows:
        # Return empty Excel
        df = pd.DataFrame(columns=["timestamp_utc", "market_id", "question", "yes_price", "no_price"])
    else:
        df = pd.DataFrame(rows)
        # Reorder columns for readability
        preferred = [
            "timestamp_utc", "market_id", "question",
            "yes_price", "no_price", "yes_cents", "no_cents",
            "spread", "volumeNum", "liquidityNum", "active", "closed",
        ]
        cols = [c for c in preferred if c in df.columns]
        cols += [c for c in df.columns if c not in cols]
        df = df[cols]

    # Write to Excel in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Snapshots")
    output.seek(0)

    # Build filename
    now_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"snapshots_{now_str}.xlsx"

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
