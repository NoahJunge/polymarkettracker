"""Collector and DCA job control API endpoints."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query, Request

router = APIRouter()


@router.post("/jobs/collect")
async def run_collector(
    request: Request,
    timestamp: Optional[str] = Query(None, description="Override snapshot timestamp (ISO 8601, e.g. 2026-03-24T12:00:00Z)"),
):
    override_time = None
    if timestamp:
        override_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if override_time.tzinfo is None:
            override_time = override_time.replace(tzinfo=timezone.utc)
    scheduler = request.app.state.scheduler
    stats = await scheduler.run_collector_now(override_time=override_time)
    return stats


@router.post("/jobs/dca")
async def run_dca(request: Request):
    scheduler = request.app.state.scheduler
    result = await scheduler.run_dca_now()
    return result


@router.get("/jobs/status")
async def get_job_status(request: Request):
    scheduler = request.app.state.scheduler
    return scheduler.get_status()
