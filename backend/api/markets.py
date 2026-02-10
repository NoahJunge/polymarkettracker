"""Market and snapshot API endpoints."""

from fastapi import APIRouter, Request, Query, HTTPException

router = APIRouter()


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
