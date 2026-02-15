# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Polymarket Trump Tracker — a Dockerized web app that discovers Trump-related Polymarket prediction markets, collects price snapshots, and supports paper trading with DCA (Dollar-Cost Averaging) strategies and P&L tracking. Elasticsearch is the single source of truth.

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
- `main.py` — App entry point. Lifespan creates ES indices, initializes settings, auto-imports seed data, starts APScheduler.
- `core/es_client.py` — All ES operations (CRUD, bulk index, search, mget, collapse). Every service depends on this.
- `core/es_indices.py` — Mappings for 7 indices (see ES Index Quick Reference below).
- `core/gamma_client.py` — Polymarket Gamma API client with retry/backoff (httpx).
- `core/scheduler.py` — APScheduler AsyncIOScheduler. Reads config from ES `settings` index. Runs DCA after every collection.
- `services/collector.py` — The main pipeline: discover markets → filter → upsert → snapshot. This is the most complex module.
- `services/paper_trading_service.py` — OPEN/CLOSE trade model. FIFO realized P&L. Uses batch ES queries (collapse + mget) for performance.
- `services/dca_service.py` — DCA (Dollar-Cost Averaging) service. Creates subscriptions, backfills historical trades from snapshots, executes daily bets. Skips closed markets.
- `services/market_service.py` — Market listing with batch-enriched prices and tracking status.
- `services/alerts_service.py` — Price alert monitoring, checked after each collection.
- `utils/filters.py` — Trump keyword matching, binary Yes/No detection.
- `utils/dedup.py` — Deterministic doc_id: `"{ISO timestamp}|{market_id}"`.
- `api/` — FastAPI routes. Services accessed via `request.app.state.*`.

**Frontend** (React 18 + Vite + Tailwind + Recharts) at `frontend/`:
- 6 pages: Dashboard, MarketDetail, Discovery, PaperTrading, Database, Settings
- API client in `src/api/client.js` — all backend calls in one file
- Vite dev server proxies `/api` to `backend:8000`

## Key Patterns

- **Snapshot dedup**: `doc_id = f"{timestamp_utc_iso}|{market_id}"` — ES rejects duplicate inserts automatically.
- **Trump filtering**: `tag_slug=trump` includes ALL markets; `tag_slug=politics` requires keyword match in question field.
- **Paper trading**: Each trade is a separate ES document with `action: OPEN|CLOSE`. Positions are computed by aggregating trades per `(market_id, side)`. FIFO realized P&L.
- **DCA (Dollar-Cost Averaging)**: Recurring daily bets. On subscription creation, backfills one OPEN trade per historical day from snapshots. Daily execution adds new trades at latest snapshot price. DCA trades stored in `paper_trades` with `metadata: { dca: true, dca_id: "<id>" }`. Integrates into the combined paper trading portfolio.
- **DCA execution timing**: Runs automatically after every collection AND at 00:30 UTC daily cron. Idempotency guard: `last_executed_date` (YYYY-MM-DD) prevents duplicate daily trades. Closed markets are skipped.
- **Batch ES queries for performance**: Use `collapse` parameter (single query → latest doc per market_id) and `mget` (batch fetch by IDs) instead of N individual queries. This is critical — the Dashboard had an N+1 query problem (344+ queries for 172 positions) that was fixed with these patterns.
- **Settings**: Single ES document `doc_id="global"` in `settings` index. Changes to schedule fields trigger `scheduler.update_schedule()`.
- **Services on app.state**: All services are instantiated in `main.py` lifespan and stored on `app.state` for route access.
- **Seed data auto-import**: On first startup (empty database), `main.py` imports `backend/seed_data/seed.xlsx` with historical snapshots, markets, and tracked markets. Use `export_seed.py` to create new seed files.

## ES Index Quick Reference

| Index | Doc ID | Purpose |
|-------|--------|---------|
| `markets` | `market_id` | Discovered market metadata |
| `snapshots_wide` | `{ts}\|{mid}` | Append-only price snapshots |
| `tracked_markets` | `market_id` | Tracking config (is_tracked, stance) |
| `paper_trades` | UUID | Individual OPEN/CLOSE trade records (includes DCA trades with metadata) |
| `settings` | `"global"` | Runtime config (schedule, keywords) |
| `alerts` | `alert_id` | Price alert definitions and trigger state |
| `dca_subscriptions` | `dca_id` | DCA subscription config (market, side, quantity, last executed date) |

## API Endpoints Quick Reference

| Group | Method | Endpoint | Description |
|-------|--------|----------|-------------|
| Markets | GET | `/api/markets` | List all discovered markets (with prices + tracking enrichment) |
| Markets | GET | `/api/markets/{id}` | Single market detail with latest snapshot |
| Tracking | POST | `/api/tracking/{id}` | Track/untrack a market |
| Paper Trading | POST | `/api/paper_trades/open` | Open a paper trade |
| Paper Trading | POST | `/api/paper_trades/close` | Close a paper trade |
| Paper Trading | GET | `/api/paper_trades/positions` | Computed open positions with P&L |
| Paper Trading | GET | `/api/paper_trades/summary` | Portfolio summary (equity, P&L) |
| Paper Trading | GET | `/api/paper_trades` | All trade history |
| DCA | POST | `/api/dca` | Create DCA subscription + backfill |
| DCA | GET | `/api/dca` | List subscriptions (`?market_id=`) |
| DCA | GET | `/api/dca/trades` | DCA trades (`?market_id=`) for chart |
| DCA | GET | `/api/dca/{id}/analytics` | DCA P&L analytics |
| DCA | POST | `/api/dca/{id}/cancel` | Cancel a DCA subscription |
| Jobs | POST | `/api/jobs/collect` | Trigger manual collection |
| Jobs | POST | `/api/jobs/dca` | Trigger manual DCA execution |
| Settings | GET/PUT | `/api/settings` | Read/update runtime config |

## Gamma API Notes

- Base URL: `https://gamma-api.polymarket.com`
- Events endpoint returns markets nested inside event objects
- `outcomes` and `outcomePrices` may come as JSON strings — need `json.loads()` parsing
- Binary markets: exactly `["Yes", "No"]` outcomes

## Testing

```bash
cd backend && pytest tests/ -v
```

Tests are pure unit tests (no ES dependency). They cover:
- `test_filters.py` — Trump keyword matching, binary market detection
- `test_dedup.py` — Snapshot dedup logic
- `test_paper_trading.py` — P&L math, position aggregation
- `test_dca.py` — DCA backfill, analytics computation, daily idempotency
