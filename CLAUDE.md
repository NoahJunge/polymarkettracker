# CLAUDE.md

This file provides context to Claude (both Claude Code and Claude.ai) about the Polymarket Trump Tracker project — a bachelor thesis at the University of Copenhagen combining academic research on political bias in prediction markets with a custom-built data collection and simulation system.

---

## 1. Academic Context

### Authors
- **Simone Skovgaard** (Student ID: wnf255), University of Copenhagen
- **Noah Wenneberg Junge** (Student ID: qxk266), University of Copenhagen

### Thesis Title
*Political Bias in Online Prediction Markets*

### Research Question
**Does systematic betting on pro-Trump outcomes in Polymarket reveal persistent political bias in market pricing?**

### Hypotheses
- **H₀ (Market Efficiency):** A systematic pro-Trump betting strategy yields zero abnormal returns over time. Any observed profits or losses are attributable to random market fluctuations.
- **H₁a (Positive Political Bias):** A systematic pro-Trump betting strategy yields persistent *positive* abnormal returns — implying Trump-related contracts are systematically *undervalued* (the market underestimates pro-Trump outcomes).
- **H₁b (Negative Political Bias):** A systematic pro-Trump betting strategy yields persistent *negative* abnormal returns — implying Trump-related contracts are systematically *overvalued*, potentially reflecting ideological overconfidence among politically aligned participants.

### Core Argument
Prediction markets are theoretically efficient information aggregation mechanisms (Hayek, Fama EMH). But political polarization may cause ideologically motivated traders to distort prices. We test this empirically using a fully automated, rule-based DCA strategy that always bets on the pro-Trump outcome across all Trump-related binary markets on Polymarket, then evaluates whether the resulting portfolio shows statistically significant abnormal returns.

---

## 2. What is Polymarket?

Polymarket is a decentralized, blockchain-based prediction market platform launched in 2020, operating on the Polygon blockchain using USDC stablecoin. Users trade binary contracts on real-world events. Contract prices lie in [0, 1] USD, representing the market-implied probability of the Yes outcome occurring. Polymarket uses decentralized oracle systems (UMA) to resolve markets based on real-world outcomes.

**Key characteristics relevant to our study:**
- Open global participation (no KYC for most users), accessible to retail and politically motivated traders alike
- Cryptocurrency-based infrastructure attracts a specific user demographic
- Trump-related markets are among the most actively traded categories on the platform
- Binary Yes/No market structure allows unambiguous directional strategy construction
- Prices are publicly available via the Gamma API in real time

---

## 3. Methodology

### 3.1 Research Design
Empirical simulation study. We combine automated data scraping with a deterministic rule-based trading simulation to produce a portfolio return time series, which is then subjected to statistical hypothesis testing.

The dataset is split into two periods following the professor's suggestion:
- **Retrospective** (before 2026-01-26): daily prices obtained post-hoc from Polymarket's CLOB API, back to each market's creation date. Represents a simulated back-test.
- **Prospective** (2026-01-26 onward): prices collected in real time using the Gamma API. Represents a genuine forward test with no look-ahead bias.

### 3.2 Market Identification & Selection

**Two-stage filter:**
1. **Tag-based:** Markets tagged `trump` on Polymarket are included unconditionally. Markets tagged `politics` are subjected to a keyword filter.
2. **Keyword filter (for `politics` tag):** Question text must contain at least one of: `trump`, `donald trump`, `djt`, `maga`, `potus`, `president trump` (case-insensitive).

**Structural filter:**
- Only **binary Yes/No markets** are included (exactly `["Yes", "No"]` outcomes). This ensures the pro-Trump direction is always unambiguous.
- Only **active (non-closed)** markets at time of collection are included.

**Result:** Approximately **149–204 markets tracked simultaneously** across the data collection period, spanning electoral outcomes, executive policy decisions, judicial appointments, economic policy measures, tariff decisions, and international relations events connected to the Trump administration.

### 3.3 Data Collection

**Two data sources are used:**

#### Gamma API (prospective — live collection)
- **Source:** `https://gamma-api.polymarket.com`
- **Method:** Automated periodic collection via APScheduler. Each run queries all Trump/politics tagged events, filters markets, and stores price snapshots.
- **Prices stored:** Both `yes_price` and `no_price` are stored **independently** from the API's `outcomePrices` array. `yes + no ≈ 1.0` (slight deviation reflects the real bid-ask spread). This is the authoritative source for prospective data.
- **Snapshot fields:** `timestamp_utc`, `market_id`, `question`, `yes_price`, `no_price`, `yes_cents`, `no_cents`, `spread`, `volumeNum`, `liquidityNum`, `active`, `closed`, `market_slug`, `source="gamma"`
- **Collection frequency:** Once daily (automatic scheduler in production)

#### CLOB API (retrospective — historical backfill)
- **Source:** `https://clob.polymarket.com/prices-history`
- **Method:** One-time backfill via `POST /api/jobs/clob-backfill`. Fetches daily (`fidelity=1440`) price history back to 2024-01-01 using `startTs` parameter.
- **Prices stored:** Only the **YES token price** is available from the CLOB history endpoint. `no_price = 1 − yes_price` exactly (no spread — this is a simplification, noted as a limitation).
- **Snapshot fields:** Same schema as Gamma snapshots, with `source="clob"` and `timestamp_utc` set to midnight UTC of each trading day.
- **Important:** CLOB V2 launched April 28, 2026 (new smart contracts, pUSD collateral). The historical data we use predates this and is unaffected.

**Deduplication:** Each snapshot is assigned `doc_id = f"{timestamp_utc}|{market_id}"`. CLOB snapshots use midnight UTC (`2025-11-15T00:00:00Z|{market_id}`); Gamma snapshots use collection time (`2026-01-26T14:30:00Z|{market_id}`). These never collide. When both exist for the same calendar day, DCA backfill takes the first-sorted (CLOB midnight < Gamma afternoon).

### 3.4 Simulation Framework (DCA Strategy)

The simulation implements a **Dollar-Cost Averaging (DCA) strategy** applied uniformly across all tracked markets:

- **Direction:** Always the **pro-Trump outcome** — which is YES on most markets but NO on some
  - YES bets: markets where Yes = pro-Trump (e.g. "Will Trump implement tariffs?" → YES)
  - NO bets: markets where No = pro-Trump (e.g. "Will Trump be impeached?" → NO = Trump survives)
  - Currently: ~161 YES subscriptions and ~69 NO subscriptions (230 total)
- **Frequency:** One trade per market per calendar day
- **Quantity:** Fixed amount per day per market (uniform across all markets)
- **Entry price:** `yes_price` (YES bets) or `no_price` (NO bets) from the most recent snapshot
- **Mark-to-market:** YES positions valued at `yes_price`; NO positions at `no_price`
- **Backfilling:** On subscription creation, one simulated trade is retroactively created per historical snapshot day. After CLOB backfill, this extends trades back to each market's creation date.
- **Idempotency:** `last_executed_date` (YYYY-MM-DD) per subscription prevents duplicate daily trades
- **Market closure:** When a market closes (resolves), the DCA subscription is auto-cancelled. Resolution at YES → `yes_price` goes to 1.0 (full payout); resolution at NO → `yes_price` goes to 0.0 (full loss)

**Why DCA?** The strategy's determinism and lack of market-specific signals means any persistent abnormal returns cannot be attributed to skill or information advantage — only to structural pricing patterns.

### 3.5 Return & Performance Measurement

**Mark-to-market approach:**
- YES position value at time t: `V_t = Q × yes_price_t`
- NO position value at time t: `V_t = Q × no_price_t`
- Unrealized P&L: `Q × (current_price_t − entry_price)`
- For DCA positions accumulated over multiple days, `avg_entry_price` = volume-weighted mean of all daily entry prices
- Realized P&L: computed using **FIFO** (First-In-First-Out) matching when positions are closed
- **Portfolio equity:** `E_t = Σ(market_value of all open positions)`
- **Daily return:** `r_t = ΔP&L_t / invested_{t-1}` (time-weighted)

### 3.6 Statistical Analysis (implemented)

All tests run in `backend/analysis/run_analysis.py`. Results visible at `/analysis` in the web app.

**Pre-analysis diagnostics (verified):**
- Shapiro-Wilk + Jarque-Bera: normality **rejected** → Bootstrap BCa and Wilcoxon as robustness checks
- Ljung-Box Q-test (lags 1, 5, 10): **no significant autocorrelation** at lag 1 → standard t-test valid
- Augmented Dickey-Fuller: series is **stationary** → t-test inference valid
- Durbin-Watson: 2.17 → no lag-1 autocorrelation

**Statistical tests:**
- **Primary:** One-sample t-test on daily returns vs. zero: `t = r̄ / (σ̂ / √T)`, α = 0.05
- **Bootstrap BCa CI:** 10,000 resamples via `scipy.stats.bootstrap`, assumption-free
- **Wilcoxon signed-rank:** non-parametric median test
- **OLS trend regression:** `total_pnl_t = α + β·t + ε_t` with HC3 robust SEs — statistically significant downward slope (p < 0.001)
- **Risk metrics:** Sharpe (√365), Sortino, Calmar, VaR 95%, CVaR 95%, max drawdown
- **Anti-Trump counterfactual:** flip YES↔NO on every trade — the $1,615 gap is the strongest directional result

**Retrospective vs Prospective split (professor's suggestion):**
- Both periods show negative mean returns (consistent direction → H₁b)
- Neither individually significant on t-test; full-series OLS trend is p < 0.001
- Consistency across periods strengthens the structural interpretation

---

## 4. Dataset — Current Numbers (as of 2026-05-06)

| Metric | Value |
|--------|-------|
| Total markets discovered (ever) | ~3,200+ |
| Markets tracked | ~149–204 |
| Total price snapshots (ES) | ~40,970 |
| Total paper trades (DCA backfill + daily) | ~27,576 |
| DCA subscriptions | 230 (161 YES, 69 NO) |
| Retrospective data start (CLOB) | 2025-07-19 (earliest market) |
| Prospective data start (live collection) | 2026-01-26 |
| Total data span | ~291 days |

### Data periods
| Period | Source | Coverage | Notes |
|--------|--------|----------|-------|
| Jul 2025 – Jan 25, 2026 | CLOB API (retrospective) | 149 markets, daily | `no_price = 1 − yes_price` (no spread) |
| Jan 26 – Feb 12, 2026 | Gamma API | Irregular | Sparse early coverage |
| Feb 13–21, 2026 | Gamma API | 120–235 markets/day | Growing coverage |
| Feb 22 – present | Gamma API (prospective, clean) | ~149–204 markets/day | Primary analysis period |

**Key data quality note:** The "clean" prospective series begins 2026-02-22 when stable daily coverage was established. The t-test primary result uses this period (T=73 obs). The full series (T=284) is the robustness check.

---

## 5. Thesis Structure & Writing Status

### Abstract — WRITTEN
### Introduction — WRITTEN (missing methodology overview, contribution paragraph, structure section)
### Literature Review — PARTIALLY WRITTEN
- ✅ Prediction Markets
- ✅ Online and Decentralized Prediction Markets
- ✅ Market Efficiency and Information Aggregation
- ⬜ Political Polarization and Ideological Bias — **TODO**
- ⬜ Bias and Inefficiencies in Prediction Markets — **TODO**

### Method — WRITTEN (drafted March 2026)
### Results — **EMPTY, TODO**
### Discussion — **EMPTY, TODO**
### Conclusion — **EMPTY, TODO**

---

## 6. Key Conceptual Points for Academic Discussion

**Why YES/NO direction matters:**
- Most markets: Yes = pro-Trump (e.g. "Will Trump implement tariffs?") → YES bet
- Some markets: No = pro-Trump (e.g. "Will Trump be impeached?") → NO bet (Trump survives)
- The system correctly uses `yes_price` for YES positions and `no_price` for NO positions in all P&L calculations
- This is verified at `paper_trading_service.py` line ~623

**YES and NO prices — important distinction:**
- **Gamma API (prospective):** Both `yes_price` and `no_price` stored independently from the `outcomePrices` array. `yes + no ≈ 1.0` but not exactly (real bid-ask spread). The spread is stored in the `spread` field.
- **CLOB API (retrospective):** Only the YES token price is available from the `/prices-history` endpoint. `no_price = 1 − yes_price` exactly. The spread is always 0 by construction. This is noted as a limitation — retrospective NO-side positions use an implied rather than observed price.

**Why the retrospective/prospective split matters:**
- Retrospective = back-test (potential look-ahead bias in market selection, no actual execution)
- Prospective = forward test (real-time prices, no look-ahead bias)
- Consistency across both periods provides stronger evidence of a structural effect

**Potential confounders:**
- Markets resolve over different time horizons
- Polymarket bans US users — affects political composition of participants
- Liquidity varies — small markets have wider spreads
- Trump-related events are clustered (correlated returns across markets)
- DCA backfill assumes liquidity was available at historical snapshot prices

---

## 7. Technical Architecture (for Claude Code)

### Stack
- **Backend:** Python FastAPI, APScheduler, httpx, Elasticsearch client, openpyxl, pandas, matplotlib, scipy, statsmodels
- **Frontend:** React 18 + Vite + Tailwind CSS + Recharts (7 pages)
- **Database:** Elasticsearch 8 (single source of truth, 7 indices)
- **Infrastructure:** Docker Compose (3 services: es, backend, frontend)
- **Data persistence:** `backend/seed_data/seed.xlsx` auto-exported and pushed to GitHub after each collection

### Build & Run
```bash
docker-compose up --build
# Frontend: http://localhost:3000  Backend: http://localhost:8000  ES: http://localhost:9200
cd backend && pytest tests/ -v   # 92 unit tests, no ES dependency
```

### ES Index Quick Reference
| Index | Doc ID | Purpose |
|-------|--------|---------|
| `markets` | `market_id` | Discovered market metadata (includes `clob_token_ids`) |
| `snapshots_wide` | `{ts}\|{mid}` | Append-only price snapshots (includes `source`: "gamma" or "clob") |
| `tracked_markets` | `market_id` | Tracking config (is_tracked, stance) |
| `paper_trades` | UUID | OPEN/CLOSE trade records (DCA trades have `metadata.dca=true`, `metadata.dca_id`) |
| `settings` | `"global"` | Runtime config (schedule, keywords) |
| `alerts` | `alert_id` | Price alert definitions |
| `dca_subscriptions` | `dca_id` | DCA config (market, side, quantity, last_executed_date) |

### Key Implementation Patterns
- **Snapshot dedup:** `doc_id = f"{timestamp_utc}|{market_id}"` — ES rejects duplicates automatically
- **CLOB vs Gamma doc_id:** CLOB uses midnight UTC (`2025-11-15T00:00:00Z|{mid}`), Gamma uses collection time. No collision. DCA backfill sorts ascending and takes first per day → CLOB always wins for historical dates.
- **Trump filtering:** `tag_slug=trump` → all markets included; `tag_slug=politics` → keyword filter on question text
- **Paper trading model:** OPEN/CLOSE documents (not position objects). Positions computed by aggregating trades per `(market_id, side)`. FIFO realized P&L.
- **YES/NO P&L:** `yes_price` used for YES positions; `no_price` for NO positions — throughout paper_trading_service.py, dca_service.py, and analysis scripts
- **DCA backfill:** On subscription creation, retroactively creates one OPEN trade per historical snapshot day. After CLOB backfill, history extends to market creation.
- **CLOB token IDs:** `clob_token_ids` stored on every market doc (populated by collector from Gamma API `clobTokenIds` field). Required to call the CLOB prices-history endpoint.
- **Batch ES performance:** `collapse` (latest doc per market_id in one query) + `mget` (batch fetch by IDs)
- **Settings:** Single ES doc `id="global"`. Schedule changes trigger `scheduler.update_schedule()` live.
- **Scheduler pipeline:** After each collection → check price alerts → execute DCA daily trades → export seed → git push

### Services Quick Reference
| Service | File | Purpose |
|---------|------|---------|
| `CollectorService` | `services/collector.py` | Gamma API collection, market discovery, snapshot storage |
| `DCAService` | `services/dca_service.py` | DCA subscriptions, backfill, daily execution, rebackfill |
| `ClobHistoryService` | `services/clob_history_service.py` | CLOB historical backfill — dormant until `POST /jobs/clob-backfill` |
| `PaperTradingService` | `services/paper_trading_service.py` | Portfolio equity curve, positions, P&L |
| `MarketService` | `services/market_service.py` | Market queries |
| `ExportService` | `services/export_service.py` | seed.xlsx export |
| `AlertsService` | `services/alerts_service.py` | Price alerts |

### API Endpoints Quick Reference
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/markets` | All discovered markets with prices + tracking status |
| GET | `/api/markets/{id}` | Single market detail |
| POST | `/api/tracking/{id}` | Track/untrack a market |
| POST | `/api/paper_trades/open` | Open a paper trade |
| POST | `/api/paper_trades/close` | Close a paper trade |
| GET | `/api/paper_trades/positions` | Open positions with P&L |
| GET | `/api/paper_trades/summary` | Portfolio summary |
| GET | `/api/paper_trades/equity-curve` | Equity curve + stats |
| POST | `/api/dca` | Create DCA subscription + backfill |
| GET | `/api/dca` | List subscriptions |
| GET | `/api/dca/{id}/analytics` | DCA P&L analytics |
| POST | `/api/dca/{id}/cancel` | Cancel subscription |
| POST | `/api/dca/{id}/rebackfill` | Delete + regenerate trades for one subscription |
| POST | `/api/dca/rebackfill-all` | Delete + regenerate trades for all active subscriptions |
| POST | `/api/jobs/collect` | Trigger manual Gamma collection |
| POST | `/api/jobs/dca` | Trigger manual DCA execution |
| POST | `/api/jobs/analysis` | Run `run_analysis.py` script, save figures + CSVs |
| POST | `/api/jobs/clob-backfill` | One-shot: fetch CLOB history → inject snapshots → rebackfill all DCA |
| GET | `/api/analysis/status` | Figure availability + last run time |
| GET | `/api/analysis/metrics` | Key metrics JSON (from CSVs) + period comparison |
| GET | `/api/analysis/figures/{filename}` | Serve a PNG figure by filename |
| GET/PUT | `/api/settings` | Read/update runtime config |

### Analysis Script
`backend/analysis/run_analysis.py` — standalone, reads only `seed_data/seed.xlsx`:
- **Sections 1–9:** Portfolio overview, diagnostics, hypothesis tests, risk metrics, cross-sectional analysis, anti-Trump counterfactual, figures, export, retrospective vs prospective comparison
- **Output:** 10 PNG figures + 4 CSVs → `backend/analysis/output/`
- **Figures:** fig1 (equity curve, full timeline with period divider), fig2 (daily P&L), fig3 (return distribution), fig4 (Q-Q), fig5 (ACF/PACF), fig6 (drawdown), fig7 (per-market P&L), fig8 (pro vs anti counterfactual), fig9 (rolling Sharpe), fig10 (retrospective vs prospective)
- **Run:** `docker-compose exec backend python3 analysis/run_analysis.py`
- **Web UI:** visible at `http://localhost:3000/analysis` (Analysis page)

### Gamma API Notes
- Base URL: `https://gamma-api.polymarket.com`
- Events endpoint returns markets nested inside event objects
- `outcomes` and `outcomePrices` come as JSON strings → need `json.loads()` parsing
- Binary markets: exactly `["Yes", "No"]` outcomes
- `yes_price + no_price ≈ 1.0` (small spread reflects real bid-ask)
- `clobTokenIds` is a JSON string (e.g. `'["123456", "789012"]'`) — the YES token is index 0

### CLOB API Notes
- Base URL: `https://clob.polymarket.com`
- History endpoint: `GET /prices-history?market={yes_token_id}&startTs={unix_ts}&fidelity=1440`
- `fidelity=1440` = daily data points (minutes)
- Returns `{"history": [{"t": unix_timestamp, "p": price}, ...]}`
- Only the YES token price is returned — NO price must be inferred as `1 − p`
- CLOB V2 launched 2026-04-28 (new contracts, pUSD). Historical data predating this is unaffected.
- Rate limit: ~4 req/sec → use 0.25s delay between requests
