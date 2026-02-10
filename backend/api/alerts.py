"""Alert API endpoints."""

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

router = APIRouter()


class CreateAlertRequest(BaseModel):
    market_id: str
    side: str  # YES or NO
    condition: str  # ABOVE or BELOW
    threshold: float  # 0-1
    note: str = ""


@router.get("/alerts")
async def list_alerts(request: Request, active_only: bool = False):
    svc = request.app.state.alerts_service
    return await svc.get_alerts(active_only=active_only)


@router.get("/alerts/triggered")
async def get_triggered_alerts(request: Request):
    svc = request.app.state.alerts_service
    return await svc.get_triggered_alerts()


@router.post("/alerts")
async def create_alert(request: Request, body: CreateAlertRequest):
    svc = request.app.state.alerts_service
    if body.side.upper() not in ("YES", "NO"):
        raise HTTPException(400, "side must be YES or NO")
    if body.condition.upper() not in ("ABOVE", "BELOW"):
        raise HTTPException(400, "condition must be ABOVE or BELOW")
    if not 0 <= body.threshold <= 1:
        raise HTTPException(400, "threshold must be between 0 and 1")
    return await svc.create_alert(
        market_id=body.market_id,
        side=body.side,
        condition=body.condition,
        threshold=body.threshold,
        note=body.note,
    )


@router.delete("/alerts/{alert_id}")
async def delete_alert(request: Request, alert_id: str):
    svc = request.app.state.alerts_service
    deleted = await svc.delete_alert(alert_id)
    if not deleted:
        raise HTTPException(404, "Alert not found")
    return {"deleted": True}


@router.post("/alerts/{alert_id}/dismiss")
async def dismiss_alert(request: Request, alert_id: str):
    svc = request.app.state.alerts_service
    ok = await svc.dismiss_alert(alert_id)
    if not ok:
        raise HTTPException(404, "Alert not found")
    return {"dismissed": True}
