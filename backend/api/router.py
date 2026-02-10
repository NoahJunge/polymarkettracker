"""Main API router — aggregates all sub-routers."""

from fastapi import APIRouter

from api.markets import router as markets_router
from api.tracking import router as tracking_router
from api.jobs import router as jobs_router
from api.paper_trading import router as paper_trading_router
from api.settings import router as settings_router
from api.alerts import router as alerts_router

api_router = APIRouter(prefix="/api")

api_router.include_router(markets_router, tags=["Markets"])
api_router.include_router(tracking_router, tags=["Tracking"])
api_router.include_router(jobs_router, tags=["Jobs"])
api_router.include_router(paper_trading_router, tags=["Paper Trading"])
api_router.include_router(settings_router, tags=["Settings"])
api_router.include_router(alerts_router, tags=["Alerts"])
