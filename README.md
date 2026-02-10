# Polymarket Trump Tracker

A full-stack web application that tracks Trump-related prediction markets on Polymarket. Features automated data collection, paper trading, price alerts, and real-time dashboards.

Built as a bachelor project using **FastAPI**, **React**, **Elasticsearch**, and **Docker**.

## Features

- **Market Discovery** — Automatically discovers Trump-related markets from Polymarket's Gamma API using configurable tag slugs and keyword filters
- **Snapshot Collection** — Scheduled collector captures price snapshots at configurable intervals, storing full history in Elasticsearch
- **Dashboard** — Overview with summary cards (biggest 24h movers, closing-soon markets, portfolio P&L), sortable market table with 24h change indicators
- **Paper Trading** — Simulate trades with FIFO P&L tracking, open/close positions, portfolio summary with realized + unrealized returns
- **Price Alerts** — Set custom price thresholds on any market; alerts trigger automatically during collection runs and appear in the notification bell
- **Auto-Refresh** — Dashboard polls every 60 seconds with a live "updated X seconds ago" indicator
- **Historical Data Import** — Import scraped Excel spreadsheet data with deduplication
- **Daily Exports** — Automated CSV exports of snapshot data

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Docker Compose)
- Git

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/NoahJunge/polymarkettracker.git
cd polymarkettracker

# 2. Start all services
docker compose up --build

# 3. Open in browser
#    Frontend: http://localhost:3000
#    Backend API: http://localhost:8000/api
#    Elasticsearch: http://localhost:9200
```

That's it. Docker Compose starts Elasticsearch, the backend, and the frontend. The collector begins discovering markets automatically.

## Architecture

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────┐
│   Frontend   │────>│     Backend      │────>│Elasticsearch │
│  React/Vite  │     │    FastAPI       │     │   8.11.0     │
│  Port 3000   │     │    Port 8000     │     │  Port 9200   │
└──────────────┘     └──────────────────┘     └──────────────┘
                           │
                           │ Scheduled
                           ▼
                     ┌──────────────┐
                     │ Gamma API    │
                     │ (Polymarket) │
                     └──────────────┘
```

### Backend (FastAPI)
- **Core**: ES client, Gamma API client, APScheduler
- **Services**: Collector, market queries, tracking, paper trading, alerts, settings, exports
- **API**: RESTful endpoints under `/api/`

### Frontend (React + Vite)
- **Pages**: Dashboard, Market Detail, Discovery, Paper Trading, Settings
- **Components**: MarketTable (sortable), PriceChart (Recharts), SummaryCards, AlertBell, TradeModal

### Elasticsearch Indices (6)
| Index | Purpose | Doc ID |
|-------|---------|--------|
| `markets` | Market metadata + latest info | `market_id` |
| `snapshots_wide` | Historical price snapshots | `{timestamp}\|{market_id}` |
| `tracked_markets` | Tracking configuration | `market_id` |
| `paper_trades` | Paper trade records | `trade_id` (UUID) |
| `settings` | Runtime configuration | `"global"` |
| `alerts` | Price alert definitions | `alert_id` (UUID) |

## How It Works

### Collector Pipeline

The collector runs on a configurable schedule (default: every 15 minutes) and:

1. Discovers events from Polymarket Gamma API using tag slugs (`trump`, `politics`)
2. From `trump` tag: includes ALL markets
3. From `politics` tag: includes only markets matching Trump keywords (configurable)
4. Filters to binary Yes/No markets (configurable)
5. Upserts market metadata to ES `markets` index (including end dates, descriptions, 24h volume)
6. For all tracked markets, fetches fresh prices and writes append-only snapshots to `snapshots_wide`
7. Uses deterministic document IDs (`{timestamp}|{market_id}`) to prevent duplicates
8. Checks all active price alerts against new data and triggers any that crossed their threshold

### Run Collector Manually

```bash
# Via API
curl -X POST http://localhost:8000/api/jobs/collect

# Check status
curl http://localhost:8000/api/jobs/status
```

Or use the "Run Collector Now" button in the Settings page.

## API Endpoints

### Markets
- `GET /api/markets?tracked=true&search=...&sort=volumeNum&order=desc`
- `GET /api/markets/summary` — Dashboard summary (movers, closing soon)
- `GET /api/markets/categories` — Available category tags
- `GET /api/markets/{id}` — Single market detail
- `GET /api/markets/{id}/snapshots?limit=500&sort=desc`
- `GET /api/new_bets?search=...&category=...&sort=volumeNum&order=desc`

### Tracking
- `GET /api/tracked_markets`
- `POST /api/tracked_markets/{id}` — Track/untrack a market

### Paper Trading
- `POST /api/paper_trades/open` — `{market_id, side, quantity}`
- `POST /api/paper_trades/close` — `{market_id, side, quantity}`
- `GET /api/paper_positions` — Open positions with mark-to-market
- `GET /api/paper_portfolio/summary` — Portfolio P&L summary
- `GET /api/paper_trades` — All trade history

### Alerts
- `GET /api/alerts` — List all alerts
- `POST /api/alerts` — `{market_id, side, condition, threshold, note}`
- `GET /api/alerts/triggered` — Unread triggered alerts
- `POST /api/alerts/{id}/dismiss` — Dismiss a triggered alert
- `DELETE /api/alerts/{id}` — Delete an alert

### Jobs & Settings
- `POST /api/jobs/collect` — Trigger immediate collection
- `GET /api/jobs/status` — Scheduler status and last run stats
- `GET /api/settings` / `POST /api/settings` — Read/update runtime settings

## Configuration

Settings are stored in Elasticsearch and editable at runtime via the Settings page:

| Setting | Default | Description |
|---------|---------|-------------|
| `collector_enabled` | `true` | Enable scheduled collection |
| `collector_interval_minutes` | `15` | Collection interval in minutes |
| `tag_slugs` | `["trump", "politics"]` | Polymarket tag slugs to scan |
| `trump_keywords` | `["trump", "donald trump", ...]` | Keywords for politics tag filtering |
| `require_binary_yes_no` | `true` | Only include Yes/No binary markets |
| `force_tracked_ids` | `[]` | Market IDs to always track |
| `export_enabled` | `true` | Enable daily CSV exports |

## Running Tests

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```

58 unit tests covering: keyword filters, binary market detection, deduplication, P&L calculations, snapshot building, and price normalization.

## Importing Historical Data

If you have scraped data in an Excel file with sheets `snapshots_wide`, `markets`, and `tracked_markets`:

```bash
docker compose exec backend python import_spreadsheet.py /path/to/data.xlsx
```

## Project Structure

```
backend/
  main.py              # FastAPI app with lifespan
  config.py            # Environment configuration
  core/
    es_client.py       # Elasticsearch operations
    es_indices.py      # Index mappings (6 indices)
    gamma_client.py    # Polymarket API client
    scheduler.py       # APScheduler manager
  services/
    collector.py       # Market discovery + snapshot pipeline
    market_service.py  # Market queries + dashboard summary
    tracking_service.py
    paper_trading_service.py
    alerts_service.py  # Price alert system
    settings_service.py
    export_service.py
  api/                 # FastAPI route handlers
  utils/               # Filters, dedup, retry logic
  tests/               # 58 unit tests

frontend/
  src/
    pages/             # Dashboard, MarketDetail, Discovery, PaperTrading, Settings
    components/        # MarketTable, PriceChart, SummaryCards, AlertBell, TradeModal, etc.
    api/client.js      # Axios API client
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.11, FastAPI, APScheduler |
| Frontend | React 18, Vite, Tailwind CSS v4, Recharts |
| Database | Elasticsearch 8.11 |
| API Client | httpx (backend), axios (frontend) |
| Infrastructure | Docker, Docker Compose |
| Testing | pytest, pytest-asyncio |

## License

This project is part of a bachelor thesis. All rights reserved.
