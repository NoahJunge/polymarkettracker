# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Polymarket Trump Tracker — a Dockerized web app that discovers Trump-related Polymarket prediction markets, collects price snapshots, and supports paper trading with P&L tracking. Elasticsearch is the single source of truth.

## Build & Run

```bash
# Start all services (ES + backend + frontend)
docker-compose up --build

# Frontend: http://localhost:3000
# Backend:  http://localhost:8000
# ES:       http://localhost:9200

# Run backend tests (from repo root or inside container)
cd backend && pytest tests/ -v

# Install backend deps locally (for IDE support / running tests outside Docker)
cd backend && pip install -r requirements.txt

# Install frontend deps locally
cd frontend && npm install
```

## Architecture

**Backend** (Python FastAPI) at `backend/`:
- `main.py` — App entry point. Lifespan creates ES indices, initializes settings, starts APScheduler.
- `core/es_client.py` — All ES operations (CRUD, bulk index, search). Every service depends on this.
- `core/es_indices.py` — Mappings for 5 indices: `markets`, `snapshots_wide`, `tracked_markets`, `paper_trades`, `settings`.
- `core/gamma_client.py` — Polymarket Gamma API client with retry/backoff (httpx).
- `core/scheduler.py` — APScheduler AsyncIOScheduler. Reads config from ES `settings` index.
- `services/collector.py` — The main pipeline: discover markets → filter → upsert → snapshot. This is the most complex module.
- `services/paper_trading_service.py` — OPEN/CLOSE trade model. FIFO realized P&L. Prices from nearest snapshot.
- `utils/filters.py` — Trump keyword matching, binary Yes/No detection.
- `utils/dedup.py` — Deterministic doc_id: `"{ISO timestamp}|{market_id}"`.
- `api/` — FastAPI routes. Services accessed via `request.app.state.*`.

**Frontend** (React 18 + Vite + Tailwind + Recharts) at `frontend/`:
- 5 pages: Dashboard, MarketDetail, Discovery, PaperTrading, Settings
- API client in `src/api/client.js` — all backend calls in one file
- Vite dev server proxies `/api` to `backend:8000`

## Key Patterns

- **Snapshot dedup**: `doc_id = f"{timestamp_utc_iso}|{market_id}"` — ES rejects duplicate inserts automatically.
- **Trump filtering**: `tag_slug=trump` includes ALL markets; `tag_slug=politics` requires keyword match in question field.
- **Paper trading**: Each trade is a separate ES document with `action: OPEN|CLOSE`. Positions are computed by aggregating trades per `(market_id, side)`.
- **Settings**: Single ES document `doc_id="global"` in `settings` index. Changes to schedule fields trigger `scheduler.update_schedule()`.
- **Services on app.state**: All services are instantiated in `main.py` lifespan and stored on `app.state` for route access.

## ES Index Quick Reference

| Index | Doc ID | Purpose |
|-------|--------|---------|
| `markets` | `market_id` | Discovered market metadata |
| `snapshots_wide` | `{ts}\|{mid}` | Append-only price snapshots |
| `tracked_markets` | `market_id` | Tracking config (is_tracked, stance) |
| `paper_trades` | UUID | Individual OPEN/CLOSE trade records |
| `settings` | `"global"` | Runtime config (schedule, keywords) |
