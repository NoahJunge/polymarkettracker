"""Tracking configuration API endpoints."""

from fastapi import APIRouter, Request

from models.tracking import TrackedMarketUpdate

router = APIRouter()


@router.get("/tracked_markets")
async def get_tracked_markets(request: Request):
    svc = request.app.state.tracking_service
    return await svc.get_tracked_markets()


@router.post("/tracked_markets/{market_id}")
async def set_tracking(request: Request, market_id: str, body: TrackedMarketUpdate):
    svc = request.app.state.tracking_service
    return await svc.set_tracking(market_id, body)
