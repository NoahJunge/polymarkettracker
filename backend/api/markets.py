"""Market and snapshot API endpoints."""

import io
from datetime import datetime, timezone

import pandas as pd
from fastapi import APIRouter, Request, Query, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse

router = APIRouter()

MARKETS_INDEX = "markets"
TRACKED_INDEX = "tracked_markets"


@router.get("/markets")
async def list_markets(
    request: Request,
    tracked: bool | None = None,
    search: str | None = None,
    category: str | None = None,
    sort: str = Query("volumeNum", regex="^(volumeNum|liquidityNum|last_seen_utc|volume|liquidity|updated|end_date|volume_24hr|one_day_price_change)$"),
    order: str = Query("desc", regex="^(asc|desc)$"),
    size: int = Query(100, ge=1, le=1000),
    from_: int = Query(0, ge=0, alias="from"),
):
    svc = request.app.state.market_service
    return await svc.list_markets(
        tracked=tracked, search=search, category=category,
        sort=sort, order=order, size=size, from_=from_,
    )


@router.get("/markets/summary")
async def get_dashboard_summary(request: Request):
    svc = request.app.state.market_service
    return await svc.get_dashboard_summary()


@router.get("/markets/categories")
async def get_categories(request: Request):
    svc = request.app.state.market_service
    return await svc.get_categories()


@router.get("/markets/{market_id}")
async def get_market(request: Request, market_id: str):
    svc = request.app.state.market_service
    market = await svc.get_market(market_id)
    if not market:
        raise HTTPException(404, "Market not found")
    return market


@router.get("/markets/{market_id}/snapshots")
async def get_snapshots(
    request: Request,
    market_id: str,
    limit: int = Query(500, ge=1, le=10000),
    from_ts: str | None = Query(None, alias="from"),
    to_ts: str | None = Query(None, alias="to"),
    sort: str = Query("desc", regex="^(asc|desc)$"),
):
    svc = request.app.state.market_service
    return await svc.get_snapshots(
        market_id=market_id, limit=limit, from_ts=from_ts, to_ts=to_ts, sort=sort
    )


@router.get("/new_bets")
async def get_new_bets(
    request: Request,
    search: str | None = None,
    category: str | None = None,
    sort: str = Query("volumeNum", regex="^(volumeNum|liquidityNum|last_seen_utc|volume|liquidity|updated|end_date|volume_24hr|one_day_price_change)$"),
    order: str = Query("desc", regex="^(asc|desc)$"),
    size: int = Query(100, ge=1, le=1000),
    from_: int = Query(0, ge=0, alias="from"),
):
    svc = request.app.state.market_service
    return await svc.get_new_bets(search=search, category=category, sort=sort, order=order, size=size, from_=from_)


@router.get("/new_bets/export")
async def export_new_bets(request: Request):
    """Export all discovered (untracked) markets as an Excel file."""
    es = request.app.state.es

    # Get tracked IDs to exclude
    tracked_result = await es.search(
        TRACKED_INDEX,
        query={"term": {"is_tracked": True}},
        size=10000,
    )
    tracked_ids = [h["_source"]["market_id"] for h in tracked_result["hits"]["hits"]]

    query: dict
    if tracked_ids:
        query = {"bool": {"must_not": [{"terms": {"market_id": tracked_ids}}]}}
    else:
        query = {"match_all": {}}

    result = await es.search(
        MARKETS_INDEX,
        query=query,
        sort=[{"volumeNum": {"order": "desc"}}],
        size=10000,
    )

    rows = [hit["_source"] for hit in result["hits"]["hits"]]

    if not rows:
        df = pd.DataFrame(columns=["market_id", "question", "yes_price", "no_price", "volumeNum"])
    else:
        df = pd.DataFrame(rows)
        preferred = [
            "market_id", "question", "yes_price", "no_price",
            "volumeNum", "liquidityNum", "volume_24hr", "one_day_price_change",
            "active", "closed", "end_date", "source_tags", "polymarket_url",
            "first_seen_utc", "last_seen_utc",
        ]
        cols = [c for c in preferred if c in df.columns]
        cols += [c for c in df.columns if c not in cols]
        df = df[cols]

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Discovery")
    output.seek(0)

    now_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"discovery_{now_str}.xlsx"

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/new_bets/export")
async def export_new_bets_filtered(request: Request, file: UploadFile = File(...)):
    """Export discovered markets excluding tracked IDs AND IDs from an uploaded Excel."""
    es = request.app.state.es

    # Parse market_ids from uploaded Excel
    contents = await file.read()
    try:
        uploaded_df = pd.read_excel(io.BytesIO(contents), engine="openpyxl")
    except Exception:
        raise HTTPException(400, "Could not parse uploaded Excel file.")

    if "market_id" not in uploaded_df.columns:
        raise HTTPException(400, "Uploaded file must contain a 'market_id' column.")

    uploaded_ids = set(uploaded_df["market_id"].dropna().astype(str).tolist())

    # Get tracked IDs to also exclude
    tracked_result = await es.search(
        TRACKED_INDEX,
        query={"term": {"is_tracked": True}},
        size=10000,
    )
    tracked_ids = {h["_source"]["market_id"] for h in tracked_result["hits"]["hits"]}

    exclude_ids = list(uploaded_ids | tracked_ids)

    query: dict
    if exclude_ids:
        query = {"bool": {"must_not": [{"terms": {"market_id": exclude_ids}}]}}
    else:
        query = {"match_all": {}}

    result = await es.search(
        MARKETS_INDEX,
        query=query,
        sort=[{"volumeNum": {"order": "desc"}}],
        size=10000,
    )

    rows = [hit["_source"] for hit in result["hits"]["hits"]]

    if not rows:
        df = pd.DataFrame(columns=["market_id", "question", "yes_price", "no_price", "volumeNum"])
    else:
        df = pd.DataFrame(rows)
        preferred = [
            "market_id", "question", "market_slug", "yes_price", "no_price",
            "volumeNum", "liquidityNum", "volume_24hr", "one_day_price_change",
            "outcomes", "description", "resolution_source",
            "active", "closed", "end_date", "source_tags", "polymarket_url",
            "first_seen_utc", "last_seen_utc",
        ]
        cols = [c for c in preferred if c in df.columns]
        cols += [c for c in df.columns if c not in cols]
        df = df[cols]

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Discovery")
    output.seek(0)

    now_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"discovery_new_{now_str}.xlsx"

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
