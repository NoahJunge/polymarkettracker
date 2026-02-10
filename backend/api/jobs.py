"""Collector job control API endpoints."""

from fastapi import APIRouter, Request

router = APIRouter()


@router.post("/jobs/collect")
async def run_collector(request: Request):
    scheduler = request.app.state.scheduler
    stats = await scheduler.run_collector_now()
    return stats


@router.get("/jobs/status")
async def get_job_status(request: Request):
    scheduler = request.app.state.scheduler
    return scheduler.get_status()
