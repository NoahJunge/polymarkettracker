"""Collector and DCA job control API endpoints."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query, Request

router = APIRouter()

# Jan 26, 2026 00:00:00 UTC — first live Gamma collection run
_PROSP_START_TS = int(datetime(2026, 1, 26, tzinfo=timezone.utc).timestamp())
# Feb 22, 2026 00:00:00 UTC — start of stable daily Gamma coverage (exclusive end for gap fill)
_CLEAN_START_TS = int(datetime(2026, 2, 22, tzinfo=timezone.utc).timestamp())


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


@router.post("/jobs/analysis")
async def run_analysis(request: Request):
    import subprocess, sys
    try:
        proc = subprocess.run(
            [sys.executable, "analysis/run_analysis.py"],
            capture_output=True, text=True, timeout=300,
            cwd="/app",
        )
        return {
            "status":       "completed" if proc.returncode == 0 else "failed",
            "returncode":   proc.returncode,
            "stdout_tail":  proc.stdout[-3000:] if proc.stdout else "",
            "stderr_tail":  proc.stderr[-1000:] if proc.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "error": "Analysis took longer than 5 minutes"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.post("/jobs/clob-backfill")
async def run_clob_backfill(
    request: Request,
    start_ts: Optional[int] = Query(None, description="Unix timestamp floor for CLOB history fetch (default: 2024-01-01)"),
    end_ts: Optional[int] = Query(None, description="Unix timestamp ceiling — points after this are skipped"),
):
    svc = request.app.state.clob_history_service
    return await svc.run_backfill(start_ts=start_ts, end_ts=end_ts)


@router.post("/jobs/fill-prospective-gaps")
async def fill_prospective_gaps(request: Request):
    """
    Fill the sparse Jan 26 – Feb 21 gap in the prospective period with CLOB daily prices.
    Injects midnight-UTC snapshots and rebackfills ALL DCA subscriptions (incl. cancelled).
    Safe to run multiple times — existing snapshot doc IDs are idempotent.
    """
    svc = request.app.state.clob_history_service
    return await svc.run_backfill(
        start_ts=_PROSP_START_TS,
        end_ts=_CLEAN_START_TS - 1,
        include_cancelled=True,
    )
