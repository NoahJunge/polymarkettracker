"""DCA (Dollar-Cost Averaging) API endpoints."""

from fastapi import APIRouter, Request, HTTPException

from models.dca import CreateDCARequest

router = APIRouter()


@router.post("/dca")
async def create_dca(request: Request, body: CreateDCARequest):
    svc = request.app.state.dca_service
    return await svc.create_subscription(body)


@router.get("/dca")
async def list_dca(request: Request, market_id: str | None = None):
    svc = request.app.state.dca_service
    return await svc.get_subscriptions(market_id=market_id)


@router.get("/dca/trades")
async def get_dca_trades(request: Request, market_id: str | None = None):
    svc = request.app.state.dca_service
    return await svc.get_dca_trades(market_id=market_id)


@router.get("/dca/{dca_id}/analytics")
async def get_dca_analytics(request: Request, dca_id: str):
    svc = request.app.state.dca_service
    analytics = await svc.get_analytics(dca_id)
    if not analytics:
        raise HTTPException(404, "DCA subscription not found")
    return analytics.model_dump(mode="json")


@router.post("/dca/{dca_id}/cancel")
async def cancel_dca(request: Request, dca_id: str):
    svc = request.app.state.dca_service
    ok = await svc.cancel_subscription(dca_id)
    if not ok:
        raise HTTPException(400, "Failed to cancel DCA subscription")
    return {"status": "cancelled", "dca_id": dca_id}
