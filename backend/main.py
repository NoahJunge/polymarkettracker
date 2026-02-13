"""FastAPI application entry point with lifespan for ES and scheduler init."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
from core.es_client import ESClient
from core.es_indices import ALL_INDICES
from core.scheduler import SchedulerManager
from core.gamma_client import GammaClient
from services.settings_service import SettingsService
from services.collector import CollectorService
from services.market_service import MarketService
from services.tracking_service import TrackingService
from services.paper_trading_service import PaperTradingService
from services.export_service import ExportService
from services.alerts_service import AlertsService
from services.dca_service import DCAService
from api.router import api_router

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    logger.info("Starting up — connecting to ES at %s", config.ES_HOST)
    es = ESClient(hosts=[config.ES_HOST])

    # Wait for ES
    for attempt in range(30):
        try:
            health = await es.health()
            logger.info("ES cluster status: %s", health.get("status"))
            break
        except Exception:
            if attempt == 29:
                raise
            import asyncio
            await asyncio.sleep(2)

    # Create indices
    for name, mapping in ALL_INDICES.items():
        await es.ensure_index(name, mapping)
    logger.info("All indices ensured")

    # Auto-import seed data on first run (empty database)
    seed_path = os.path.join(os.path.dirname(__file__), "seed_data", "seed.xlsx")
    if os.path.exists(seed_path):
        snap_count = await es.count("snapshots_wide")
        if snap_count == 0:
            logger.info("Empty database detected — importing seed data from %s", seed_path)
            try:
                from import_spreadsheet import import_all
                await import_all(seed_path)
                logger.info("Seed data import complete")
            except Exception as e:
                logger.error("Seed data import failed: %s", e)

    # Init services
    gamma = GammaClient()
    settings_svc = SettingsService(es)
    await settings_svc.ensure_defaults()

    collector_svc = CollectorService(es, gamma, settings_svc)
    market_svc = MarketService(es)
    tracking_svc = TrackingService(es)
    paper_svc = PaperTradingService(es)
    export_svc = ExportService(es, config.EXPORT_DIR)
    alerts_svc = AlertsService(es)
    dca_svc = DCAService(es)

    # Scheduler
    scheduler = SchedulerManager(es, settings_svc, collector_svc, export_svc, alerts_svc, dca_svc)
    await scheduler.start()

    # Store on app state
    app.state.es = es
    app.state.gamma = gamma
    app.state.settings_service = settings_svc
    app.state.collector_service = collector_svc
    app.state.market_service = market_svc
    app.state.tracking_service = tracking_svc
    app.state.paper_trading_service = paper_svc
    app.state.export_service = export_svc
    app.state.alerts_service = alerts_svc
    app.state.dca_service = dca_svc
    app.state.scheduler = scheduler

    logger.info("Backend ready")

    yield

    # --- Shutdown ---
    logger.info("Shutting down")
    await scheduler.shutdown()
    await gamma.close()
    await es.close()


app = FastAPI(title="Polymarket Trump Tracker", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
