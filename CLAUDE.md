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
Prediction markets are theoretically efficient information aggregation mechanisms (Hayek, Fama EMH). But political polarization may cause ideologically motivated traders to distort prices. We test this empirically using a fully automated, rule-based DCA strategy that always bets YES (pro-Trump) across all Trump-related binary markets on Polymarket, then evaluates whether the resulting portfolio shows statistically significant abnormal returns.

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

### 3.2 Market Identification & Selection

**Two-stage filter:**
1. **Tag-based:** Markets tagged `trump` on Polymarket are included unconditionally. Markets tagged `politics` are subjected to a keyword filter.
2. **Keyword filter (for `politics` tag):** Question text must contain at least one of: `trump`, `donald trump`, `djt`, `maga`, `potus`, `president trump` (case-insensitive).

**Structural filter:**
- Only **binary Yes/No markets** are included (exactly `["Yes", "No"]` outcomes). This ensures the "Yes" outcome always represents an unambiguous pro-Trump directional bet.
- Only **active (non-closed)** markets at time of collection are included.

**Result:** Approximately **196–204 markets tracked simultaneously** across the data collection period, spanning electoral outcomes, executive policy decisions, judicial appointments, economic policy measures, tariff decisions, and international relations events connected to the Trump administration.

### 3.3 Data Collection
- **Source:** Polymarket Gamma API (`https://gamma-api.polymarket.com`)
- **Method:** Automated periodic collection via APScheduler (AsyncIOScheduler). Each run queries the API for all Trump/politics tagged events, filters markets, and stores price snapshots.
- **Snapshot fields per market per collection:** `timestamp_utc`, `market_id`, `question`, `yes_price`, `no_price`, `yes_cents`, `no_cents`, `spread`, `volumeNum`, `liquidityNum`, `active`, `closed`, `market_slug`
- **Deduplication:** Each snapshot is assigned `doc_id = f"{timestamp_utc}|{market_id}"` — deterministic, so re-running collection never creates duplicates
- **Storage:** Elasticsearch (single source of truth), backed up to GitHub via `seed.xlsx`
- **Collection frequency:** Approximately once daily (manual triggers during development, automatic scheduler in production)

### 3.4 Simulation Framework (DCA Strategy)

The simulation implements a **Dollar-Cost Averaging (DCA) strategy** applied uniformly across all tracked markets:

- **Direction:** Always YES (pro-Trump outcome) — never NO
- **Frequency:** One trade per market per calendar day
- **Quantity:** Fixed amount per day per market (uniform across all markets)
- **Entry price:** `yes_price` from the most recent snapshot at time of execution
- **Backfilling:** On subscription creation, one simulated trade is retroactively created per historical snapshot day, using the `yes_price` at that day's snapshot. This maximizes the observable return time series.
- **Idempotency:** `last_executed_date` (YYYY-MM-DD) per subscription prevents duplicate daily trades
- **Market closure:** When a market closes (resolves), the DCA subscription is auto-cancelled. Resolution at YES → `yes_price` goes to 1.0 (full payout); resolution at NO → `yes_price` goes to 0.0 (full loss)

**Why DCA?** The strategy's determinism and lack of market-specific signals means any persistent abnormal returns cannot be attributed to skill or information advantage — only to structural pricing patterns.

### 3.5 Return & Performance Measurement

**Mark-to-market approach:**
- Position value at time t: `V_t = Q × yes_price_t`
- Unrealized P&L: `Q × (yes_price_t − yes_price_entry)`
- For DCA positions accumulated over multiple days, `avg_entry_price` = volume-weighted mean of all daily entry prices
- Realized P&L: computed using **FIFO** (First-In-First-Out) matching when positions are closed
- **Portfolio equity:** `E_t = Σ(market_value of all open positions)`
- **Total P&L:** `unrealized_pnl + realized_pnl` across all markets

**Computed portfolio statistics (already implemented in system):**
- Win rate (% of closed positions profitable)
- Profit factor (gross profit / gross loss)
- Sharpe ratio
- Maximum drawdown
- Average win / average loss
- **Linear regression on equity curve** (slope, R², p-value) to test for statistically significant trend
- Monte Carlo simulation (random market subsampling at varying portfolio sizes)

### 3.6 Statistical Analysis (planned)
- **Primary test:** One-sample t-test on daily portfolio returns vs. zero: `t = r̄ / (σ̂ / √T)`
- **Significance levels:** α = 0.05 and α = 0.01
- **Risk-adjusted performance:** Sharpe ratio
- **Trend analysis:** Linear regression on cumulative equity curve (p-value for slope coefficient)
- **Robustness:** Monte Carlo subsampling to evaluate whether results are driven by a small number of markets or are portfolio-wide

---

## 4. Dataset — Actual Numbers (as of 2026-03-31)

| Metric | Value |
|--------|-------|
| Total markets discovered (ever) | 3,224 |
| Unique markets with price history | 480 |
| Markets tracked simultaneously | ~196–204 |
| Total price snapshots | 16,427 |
| Total paper trades (DCA backfill + daily) | 7,036 |
| DCA subscriptions | 202 |
| Data collection start | 2026-01-26 |
| Data collection end (current) | 2026-03-31 |
| Total data span | ~65 days |

### Snapshot Coverage by Period
| Period | Markets/day | Notes |
|--------|-------------|-------|
| Jan 26 | 252 | Single snapshot, earliest data point |
| Feb 2 | 249 | Gap between Jan 26 and Feb 2 |
| Feb 5–12 | 17–30 | Sparse coverage, partial collection |
| Feb 13–20 | 120–235 | Growing coverage as system scaled |
| Feb 22–28 | 206–215 | Stable ~206 market tracking |
| Mar 1–18 | 182–200 | ~182 markets tracked daily |
| Mar 19–31 | 196–204 | Current stable tracking level |

**Important data quality note:** The early collection period (Jan 26 – Feb 12) has irregular coverage with gaps and varying market counts. The more reliable continuous daily coverage begins ~February 22, giving approximately **37 days of consistent daily snapshots** through March 31.

---

## 5. Thesis Structure & Writing Status

### Abstract — WRITTEN
Covers: data collection framework, simulation of rule-based pro-Trump strategy, price tracking, statistical analysis to detect abnormal returns, contribution to market efficiency literature.

### Introduction — WRITTEN (missing 3 items)
- Brief methodology overview paragraph — **TODO**
- Contribution paragraph (simulation framework + empirical evidence on ideological bias) — **TODO**
- Report structure section — **TODO**

### Literature Review — PARTIALLY WRITTEN
- ✅ Prediction Markets (Wolfers & Zitzewitz, Iowa Electronic Markets)
- ✅ Online and Decentralized Prediction Markets (blockchain, Augur, Gnosis, Polymarket)
- ✅ Market Efficiency and Information Aggregation (Hayek, Fama EMH, Grossman-Stiglitz)
- ⬜ Political Polarization and Ideological Bias — **EMPTY, TODO**
- ⬜ Bias and Inefficiencies in Prediction Markets — **EMPTY, TODO**

### Method — WRITTEN (drafted March 2026)
Five subsections: Research Design, Data Collection, Market Identification & Selection, Simulation Framework (DCA), Return & Performance Measurement, Statistical Analysis.

### Results — **EMPTY, TODO**
### Discussion — **EMPTY, TODO**
### Conclusion — **EMPTY, TODO**

---

## 6. Key Conceptual Points for Academic Discussion

**Why Polymarket specifically?**
- One of the largest real-money prediction markets globally
- Trump-related markets are highly liquid and numerous
- Open participation means politically motivated retail traders can freely participate
- Blockchain infrastructure provides full price transparency and audit trail

**Why the YES side = pro-Trump?**
- Every tracked market is framed as a binary Yes/No question about a Trump-related outcome
- "Yes" always represents the directional bet aligned with Trump's success/position
- Examples: "Will Trump implement 25% tariffs?", "Will Trump fire Powell?", "Will Trump win [state]?"
- Betting YES systematically = acting as if you are a Trump-aligned ideological trader

**Why DCA (not a one-time bet)?**
- DCA is the natural model for an ideologically motivated retail investor — they buy in repeatedly as they follow political news
- Daily fixed-amount buying is the simplest possible rule-based strategy
- Removes timing decisions entirely, making results attributable to market structure not skill
- Allows portfolio construction across 200 markets simultaneously

**The efficient market null hypothesis in this context:**
- If EMH holds: `yes_price` already reflects the true probability of the Yes outcome resolving
- DCA at fair prices → expected return ≈ 0 (minus any bid-ask spread friction)
- Persistent positive returns → market systematically underestimates pro-Trump outcomes (prices too low)
- Persistent negative returns → market systematically overestimates pro-Trump outcomes (prices too high, bias toward Trump from ideological traders inflating prices)

**Potential confounders to discuss:**
- Markets resolve over different time horizons (short-term events vs. multi-month policy questions)
- Polymarket bans US users, which may affect the political composition of participants
- Liquidity varies enormously across markets — small markets may have wider spreads
- Trump-related events are clustered (many markets respond to the same news simultaneously)
- The DCA backfill treats historical snapshots as if trades were placed at those prices, which assumes liquidity was available — a simplification

---

## 7. Technical Architecture (for Claude Code)

### Stack
- **Backend:** Python FastAPI, APScheduler, httpx, Elasticsearch client, openpyxl, pandas, matplotlib
- **Frontend:** React 18 + Vite + Tailwind CSS + Recharts (6 pages)
- **Database:** Elasticsearch 8 (single source of truth, 7 indices)
- **Infrastructure:** Docker Compose (3 services: es, backend, frontend)
- **Data persistence:** `backend/seed_data/seed.xlsx` auto-exported and pushed to GitHub after each collection

### Build & Run
```bash
docker-compose up --build
# Frontend: http://localhost:3000  Backend: http://localhost:8000  ES: http://localhost:9200
cd backend && pytest tests/ -v   # 58 unit tests, no ES dependency
```

### ES Index Quick Reference
| Index | Doc ID | Purpose |
|-------|--------|---------|
| `markets` | `market_id` | Discovered market metadata |
| `snapshots_wide` | `{ts}\|{mid}` | Append-only price snapshots |
| `tracked_markets` | `market_id` | Tracking config (is_tracked, stance) |
| `paper_trades` | UUID | OPEN/CLOSE trade records (DCA trades have `metadata.dca=true`) |
| `settings` | `"global"` | Runtime config (schedule, keywords) |
| `alerts` | `alert_id` | Price alert definitions |
| `dca_subscriptions` | `dca_id` | DCA config (market, side, quantity, last_executed_date) |

### Key Implementation Patterns
- **Snapshot dedup:** `doc_id = f"{timestamp_utc}|{market_id}"` — ES rejects duplicates automatically
- **Trump filtering:** `tag_slug=trump` → all markets included; `tag_slug=politics` → keyword filter on question text
- **Paper trading model:** OPEN/CLOSE documents (not position objects). Positions computed by aggregating trades per `(market_id, side)`. FIFO realized P&L.
- **DCA backfill:** On subscription creation, retroactively creates one OPEN trade per historical snapshot day
- **Batch ES performance:** `collapse` (latest doc per market_id in one query) + `mget` (batch fetch by IDs) — critical for the dashboard which otherwise had N+1 query problems
- **Settings:** Single ES doc `id="global"`. Schedule changes trigger `scheduler.update_schedule()` live.
- **Scheduler pipeline:** After each collection → check price alerts → execute DCA daily trades → export seed → git push

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
| GET | `/api/paper_trades/equity-curve` | Equity curve + stats (Sharpe, drawdown, regression) |
| POST | `/api/dca` | Create DCA subscription + backfill |
| GET | `/api/dca` | List subscriptions |
| GET | `/api/dca/{id}/analytics` | DCA P&L analytics |
| POST | `/api/dca/{id}/cancel` | Cancel subscription |
| POST | `/api/jobs/collect` | Trigger manual collection |
| POST | `/api/jobs/dca` | Trigger manual DCA execution |
| GET/PUT | `/api/settings` | Read/update runtime config |

### Gamma API Notes
- Base URL: `https://gamma-api.polymarket.com`
- Events endpoint returns markets nested inside event objects
- `outcomes` and `outcomePrices` come as JSON strings → need `json.loads()` parsing
- Binary markets: exactly `["Yes", "No"]` outcomes
- `yes_price + no_price ≈ 1.0` (small spread may cause minor deviation)
