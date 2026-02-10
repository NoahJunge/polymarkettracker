"""Settings API endpoints."""

from fastapi import APIRouter, Request

from models.settings import SettingsUpdate

router = APIRouter()


@router.get("/settings")
async def get_settings(request: Request):
    svc = request.app.state.settings_service
    settings = await svc.get()
    return settings.model_dump(mode="json")


@router.post("/settings")
async def update_settings(request: Request, body: SettingsUpdate):
    svc = request.app.state.settings_service
    updated = await svc.update(body)

    # If schedule-related settings changed, update the scheduler
    schedule_fields = {"collector_enabled", "collector_interval_minutes", "cron_expression"}
    changed_fields = set(body.model_dump(exclude_none=True).keys())
    if changed_fields & schedule_fields:
        scheduler = request.app.state.scheduler
        await scheduler.update_schedule()

    return updated.model_dump(mode="json")


@router.get("/exports")
async def list_exports(request: Request):
    svc = request.app.state.export_service
    return await svc.list_exports()
