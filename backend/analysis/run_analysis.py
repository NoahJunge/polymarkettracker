"""
╔══════════════════════════════════════════════════════════════════════════════╗
║     Polymarket Trump Tracker — Comprehensive Analysis Script                ║
║     Bachelor Thesis: "Political Bias in Online Prediction Markets"          ║
║     University of Copenhagen                                                ║
║     Authors: Simone Skovgaard (wnf255) & Noah Wenneberg Junge (qxk266)     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Run:    python3 analysis/run_analysis.py                                   ║
║  Input:  backend/seed_data/seed.xlsx                                        ║
║  Output: analysis/output/  (9 figures + results CSV)                        ║
╚══════════════════════════════════════════════════════════════════════════════╝

STRATEGY DESCRIPTION
────────────────────
A Dollar-Cost Averaging (DCA) strategy is simulated across all Trump-related
binary markets on Polymarket. One fixed-size trade is placed per market per day,
always betting on the pro-Trump outcome. For markets where "Yes" = pro-Trump
(e.g. "Will Trump implement tariffs?") we hold YES positions; for markets where
"No" = pro-Trump (e.g. "Will Trump be impeached?") we hold NO positions.

All positions are marked to market daily. Since no market has closed/resolved
yet, all P&L is unrealised.

RESEARCH QUESTION
─────────────────
Does systematic betting on pro-Trump outcomes yield abnormal returns?
  H₀ : μ = 0  (no abnormal returns — consistent with market efficiency)
  H₁a: μ > 0  (positive abnormal returns — market undervalues Trump outcomes)
  H₁b: μ < 0  (negative abnormal returns — market overvalues Trump outcomes)
"""

# ── IMPORTS ───────────────────────────────────────────────────────────────────
import json
import os
import sys
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
from matplotlib.gridspec import GridSpec
from scipy.stats import probplot

import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import bootstrap as scipy_bootstrap
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.stattools import adfuller
from statsmodels.stats.stattools import durbin_watson
import statsmodels.api as sm

warnings.filterwarnings("ignore")

# ── CONFIGURATION ─────────────────────────────────────────────────────────────
SEED_PATH          = Path(__file__).parent.parent / "seed_data" / "seed.xlsx"
OUTPUT_DIR         = Path(__file__).parent / "output"
FIGURES_DIR        = OUTPUT_DIR / "figures"
PROSPECTIVE_START  = "2026-01-26"   # date live collection began
CLEAN_START        = "2026-02-22"   # reliable continuous prospective coverage
FIGURE_DPI         = 300
ALPHA              = 0.05           # significance level

# Thesis colour palette
C_PRO    = "#7c3aed"   # violet  — pro-Trump strategy
C_GAIN   = "#16a34a"   # green
C_LOSS   = "#dc2626"   # red
C_INV    = "#3b82f6"   # blue    — invested capital
C_GRID   = "#e5e7eb"
C_TEXT   = "#111827"


# ── HELPERS ───────────────────────────────────────────────────────────────────
def norm_id(x):
    try:
        return str(int(float(x)))
    except Exception:
        return str(x)


def hline(char="─", width=70):
    print(char * width)


def section(title):
    print()
    hline("═")
    print(f"  {title}")
    hline("═")


def subsection(title):
    print(f"\n  ── {title}")
    print()


def pct(x):
    return f"{x*100:.4f}%"


def usd(x):
    return f"${x:,.4f}"


def fmt_p(p):
    if p < 0.001:
        return "p < 0.001"
    return f"p = {p:.4f}"


def significance_stars(p):
    if p < 0.01:
        return "***"
    if p < 0.05:
        return "**"
    if p < 0.10:
        return "*"
    return "(ns)"


# ── DATA LOADING ──────────────────────────────────────────────────────────────
def load_data():
    print(f"\n  Loading data from {SEED_PATH} …")
    trades = pd.read_excel(SEED_PATH, sheet_name="paper_trades")
    snaps  = pd.read_excel(SEED_PATH, sheet_name="snapshots_wide")
    subs   = pd.read_excel(SEED_PATH, sheet_name="dca_subscriptions")
    mkts   = pd.read_excel(SEED_PATH, sheet_name="markets")

    # Parse metadata and filter to DCA trades
    trades["meta"] = trades["metadata"].apply(
        lambda x: json.loads(x) if isinstance(x, str) else (x if isinstance(x, dict) else {})
    )
    dca = trades[trades["meta"].apply(lambda x: x.get("dca") == True)].copy()

    # Normalise market IDs (Excel stores them as floats)
    for df in [dca, snaps, subs, mkts]:
        df["market_id"] = df["market_id"].apply(norm_id)

    dca["side"]     = dca["side"].str.upper()
    dca["action"]   = dca["action"].str.upper()
    dca["price"]    = pd.to_numeric(dca["price"],    errors="coerce")
    dca["quantity"] = pd.to_numeric(dca["quantity"], errors="coerce")
    dca["date"]     = pd.to_datetime(dca["created_at_utc"], format="mixed", utc=True).dt.date

    snaps["date"]      = pd.to_datetime(snaps["timestamp_utc"], format="mixed", utc=True).dt.date
    snaps["yes_price"] = pd.to_numeric(snaps["yes_price"], errors="coerce")
    snaps["no_price"]  = pd.to_numeric(snaps["no_price"],  errors="coerce")

    print(f"  DCA trades:   {len(dca):,}  ({dca['side'].value_counts().to_dict()})")
    print(f"  Snapshots:    {len(snaps):,}  across {snaps['date'].nunique()} dates")
    print(f"  Subscriptions:{len(subs):,}  ({subs['side'].value_counts().to_dict()})")
    return dca, snaps, subs, mkts


# ── DAILY PRICE TABLE ─────────────────────────────────────────────────────────
def build_price_table(snaps):
    """Last snapshot per (market_id, date). Returns lookup dict and pivot table."""
    daily = (
        snaps.sort_values("timestamp_utc" if "timestamp_utc" in snaps.columns else "date")
             .groupby(["market_id", "date"])
             .last()
             .reset_index()[["market_id", "date", "yes_price", "no_price"]]
    )
    price_lookup = {}
    for row in daily.itertuples(index=False):
        price_lookup[(row.market_id, row.date)] = {
            "yes_price": row.yes_price,
            "no_price":  row.no_price,
        }
    return daily, price_lookup


# ── EQUITY CURVE RECONSTRUCTION ───────────────────────────────────────────────
def build_equity_curve(dca, price_lookup, flip_sides=False):
    """
    Replay all DCA OPEN trades chronologically, mark positions to market each day.

    flip_sides=True: Simulate having bet the OPPOSITE direction on every market
    (anti-Trump counterfactual). Entry prices are taken from the snapshot on the
    trade date using the opposite side's price.

    YES positions are valued at yes_price; NO positions at no_price.
    Since no markets have resolved, all P&L is unrealised (0 CLOSE trades).
    """
    opens = dca[dca["action"] == "OPEN"].sort_values("date").copy()
    all_dates = sorted(price_lookup.keys(), key=lambda x: x[1])
    if not all_dates:
        return pd.DataFrame()

    date_range = pd.date_range(
        opens["date"].min(), max(k[1] for k in all_dates), freq="D"
    ).date

    lots        = {}          # (market_id, effective_side) -> [(qty, entry_price)]
    last_prices = {}          # market_id -> {yes_price, no_price}
    opens_by_date = opens.groupby("date")

    # Pre-populate last_prices with latest known prices
    for (mid, d), prices in sorted(price_lookup.items(), key=lambda x: x[0][1]):
        last_prices[mid] = prices

    # Reset and replay
    last_prices = {}
    curve = []

    for d in date_range:
        # Update last known prices for this date
        for mid in set(k[0] for k in price_lookup if k[1] == d):
            last_prices[mid] = price_lookup[(mid, d)]

        # Process new OPEN trades on this date
        if d in opens_by_date.groups:
            for row in opens_by_date.get_group(d).itertuples(index=False):
                mid           = row.market_id
                orig_side     = row.side
                eff_side      = ("NO" if orig_side == "YES" else "YES") if flip_sides else orig_side

                if flip_sides:
                    # Use the opposite side's price at entry date as cost basis
                    snap = price_lookup.get((mid, d)) or last_prices.get(mid)
                    if snap:
                        entry_price = snap["no_price"] if orig_side == "YES" else snap["yes_price"]
                    else:
                        entry_price = 1.0 - row.price   # fallback: complement
                else:
                    entry_price = row.price

                key = (mid, eff_side)
                if key not in lots:
                    lots[key] = []
                lots[key].append((row.quantity, entry_price))

        # Mark all open positions to market
        portfolio_value = 0.0
        invested        = 0.0
        for (mid, side), position_lots in lots.items():
            total_qty = sum(q for q, _ in position_lots)
            if total_qty < 1e-9:
                continue
            cost   = sum(q * p for q, p in position_lots)
            prices = last_prices.get(mid)
            if prices:
                cp = prices["yes_price"] if side == "YES" else prices["no_price"]
                if np.isnan(cp):
                    cp = cost / total_qty   # fallback to avg entry
            else:
                cp = cost / total_qty       # no snapshot yet — use entry price

            portfolio_value += total_qty * cp
            invested        += cost

        total_pnl = portfolio_value - invested
        curve.append({
            "date":            d,
            "portfolio_value": portfolio_value,
            "invested":        invested,
            "total_pnl":       total_pnl,
        })

    df = pd.DataFrame(curve)
    df["date"] = pd.to_datetime(df["date"])

    # Daily P&L change
    df["daily_pnl_change"] = df["total_pnl"].diff()

    # Time-weighted daily return: P&L change / prior day invested
    prior_inv = df["invested"].shift(1)
    df["daily_return"] = np.where(
        prior_inv > 1.0,
        df["daily_pnl_change"] / prior_inv,
        np.nan
    )

    # Running drawdown (peak-to-trough as %)
    pv = df["portfolio_value"].values
    peak = np.maximum.accumulate(np.where(pv > 0, pv, np.nan))
    df["drawdown_pct"] = np.where(peak > 0, (pv - peak) / peak * 100, 0.0)

    return df


# ── PER-MARKET P&L MATRICES (for Monte Carlo) ────────────────────────────────

def build_per_market_pnl_curves(dca, price_lookup):
    """
    Decompose portfolio P&L into per-market YES/NO contributions.
    Returns matrices needed for the vectorized Monte Carlo simulation.
    """
    opens = dca[dca["action"] == "OPEN"].sort_values("date").copy()

    all_dates = sorted(set(k[1] for k in price_lookup))
    if not all_dates or len(opens) == 0:
        return [], [], np.zeros((0, 0)), np.zeros((0, 0)), np.zeros((0, 0)), np.zeros((0, 0))

    date_range = list(pd.date_range(opens["date"].min(), all_dates[-1], freq="D").date)
    T = len(date_range)

    markets = sorted(opens["market_id"].unique())
    M = len(markets)
    mkt_idx = {m: i for i, m in enumerate(markets)}

    # Pre-index price_lookup by date for O(1) daily lookups
    dates_to_prices = {}
    for (mid, d), prices in price_lookup.items():
        if mid in mkt_idx:
            dates_to_prices.setdefault(d, []).append((mid, prices))

    yes_total_qty  = np.zeros(M)
    no_total_qty   = np.zeros(M)
    yes_total_cost = np.zeros(M)
    no_total_cost  = np.zeros(M)

    yes_pnl  = np.zeros((M, T))
    no_pnl   = np.zeros((M, T))
    yes_cost = np.zeros((M, T))
    no_cost  = np.zeros((M, T))

    last_yes = np.full(M, np.nan)
    last_no  = np.full(M, np.nan)

    opens_by_date = opens.groupby("date")

    for t, d in enumerate(date_range):
        # Update last known prices for this date
        for mid, p in dates_to_prices.get(d, []):
            mi = mkt_idx[mid]
            yp = p.get("yes_price", np.nan)
            np_ = p.get("no_price", np.nan)
            if not np.isnan(yp):
                last_yes[mi] = yp
            if not np.isnan(np_):
                last_no[mi] = np_

        # New DCA trades on this date — add to both YES and NO lot trackers
        if d in opens_by_date.groups:
            for row in opens_by_date.get_group(d).itertuples(index=False):
                mid = row.market_id
                if mid not in mkt_idx:
                    continue
                mi = mkt_idx[mid]
                snap = price_lookup.get((mid, d))
                yp  = (snap["yes_price"] if snap and not np.isnan(snap.get("yes_price", np.nan))
                       else (last_yes[mi] if not np.isnan(last_yes[mi]) else row.price))
                np_ = (snap["no_price"]  if snap and not np.isnan(snap.get("no_price", np.nan))
                       else (last_no[mi]  if not np.isnan(last_no[mi])  else 1.0 - row.price))
                yes_total_qty[mi]  += row.quantity
                no_total_qty[mi]   += row.quantity
                yes_total_cost[mi] += row.quantity * yp
                no_total_cost[mi]  += row.quantity * np_

        # Vectorized mark-to-market
        yes_pnl[:, t]  = np.where(~np.isnan(last_yes),
                                   yes_total_qty * last_yes - yes_total_cost, 0.0)
        no_pnl[:, t]   = np.where(~np.isnan(last_no),
                                   no_total_qty  * last_no  - no_total_cost,  0.0)
        yes_cost[:, t] = yes_total_cost
        no_cost[:, t]  = no_total_cost

    return markets, date_range, yes_pnl, no_pnl, yes_cost, no_cost


def build_neutral_mc(yes_pnl, no_pnl, yes_cost, no_cost, n_sims=10_000, seed=42):
    """
    Vectorized 50/50 random-direction Monte Carlo.

    For each simulation, each market is independently assigned YES or NO with equal
    probability. Entry prices, costs, and daily returns are computed from the
    pre-built per-market matrices.

    Returns:
        dr_sims          : (n_sims, T-1) daily returns per simulation
        mean_return_sims : (n_sims,) mean daily return per simulation
        pnl_sims         : (n_sims, T) cumulative P&L per simulation
    """
    M, T = yes_pnl.shape
    rng = np.random.default_rng(seed)
    D = rng.integers(0, 2, size=(n_sims, M))  # 0=YES, 1=NO per market

    delta_pnl  = no_pnl  - yes_pnl    # (M, T)
    delta_cost = no_cost - yes_cost    # (M, T)
    base_pnl   = yes_pnl.sum(axis=0)  # (T,) all-YES portfolio P&L
    base_cost  = yes_cost.sum(axis=0) # (T,) all-YES total cost

    pnl_sims  = D.astype(np.float32) @ delta_pnl.astype(np.float32)  + base_pnl   # (n_sims, T)
    cost_sims = D.astype(np.float32) @ delta_cost.astype(np.float32) + base_cost  # (n_sims, T)

    dpnl      = np.diff(pnl_sims,  axis=1)   # (n_sims, T-1)
    cost_prev = cost_sims[:, :-1]             # (n_sims, T-1)
    dr_sims   = np.where(cost_prev > 1.0, dpnl / cost_prev, np.nan).astype(np.float64)

    mean_return_sims = np.nanmean(dr_sims, axis=1)

    return dr_sims, mean_return_sims, pnl_sims.astype(np.float64)


def compute_abnormal_returns(curve, dr_sims):
    """
    AR_t = R_actual_t - mean(R_neutral_t across all simulations).

    Aligns by taking the last T_actual daily returns from the MC matrix
    (the MC covers the full period; the curve may start later or have leading NaNs).
    """
    r_actual = curve["daily_return"].dropna().values
    T_actual = len(r_actual)
    r_neutral_mean = np.nanmean(dr_sims, axis=0)[-T_actual:]
    ar_series = r_actual - r_neutral_mean
    return ar_series, r_actual, r_neutral_mean


# ── PER-MARKET P&L ────────────────────────────────────────────────────────────
def compute_per_market_pnl(dca, price_lookup, snaps):
    """Unrealised P&L per market using latest available snapshot price."""
    opens  = dca[dca["action"] == "OPEN"].copy()
    latest = (
        snaps.sort_values("date")
             .groupby("market_id")
             .last()
             .reset_index()[["market_id", "yes_price", "no_price"]]
    )
    latest_map = {row.market_id: {"yes_price": row.yes_price, "no_price": row.no_price}
                  for row in latest.itertuples(index=False)}

    result = []
    for (mid, side), grp in opens.groupby(["market_id", "side"]):
        total_qty   = grp["quantity"].sum()
        total_cost  = (grp["quantity"] * grp["price"]).sum()
        avg_entry   = total_cost / total_qty if total_qty > 0 else 0
        prices      = latest_map.get(mid, {})
        current     = prices.get("yes_price" if side == "YES" else "no_price", avg_entry)
        if np.isnan(current):
            current = avg_entry
        unrealised  = total_qty * (current - avg_entry)
        result.append({
            "market_id":    mid,
            "side":         side,
            "total_qty":    total_qty,
            "avg_entry":    avg_entry,
            "current_price":current,
            "unrealised_pnl": unrealised,
        })

    df = pd.DataFrame(result).sort_values("unrealised_pnl")
    return df


# ── RISK METRICS ──────────────────────────────────────────────────────────────
def compute_risk_metrics(curve, label=""):
    r   = curve["daily_return"].dropna().values
    pnl = curve["total_pnl"].values
    inv = curve["invested"].values

    T      = len(r)
    mean_r = r.mean()
    std_r  = r.std(ddof=1)

    # Annualised return & Sharpe (√365 — prediction markets are 365-day)
    ann_return = mean_r * 365
    sharpe_ann = (mean_r / std_r) * np.sqrt(365) if std_r > 0 else np.nan

    # Sortino — downside deviation only
    downside   = r[r < 0]
    down_dev   = np.sqrt(np.mean(downside**2)) if len(downside) > 0 else np.nan
    sortino    = (mean_r / down_dev) * np.sqrt(365) if down_dev and down_dev > 0 else np.nan

    # Maximum drawdown (absolute $ and % of portfolio value)
    pv_vals    = curve["portfolio_value"].values
    peak_pv    = np.maximum.accumulate(np.where(pv_vals > 0, pv_vals, np.nan))
    dd_vals    = np.where(peak_pv > 0, (pv_vals - peak_pv) / peak_pv * 100, 0.0)
    max_dd_pct = float(np.nanmin(dd_vals))
    max_dd_usd = float(np.nanmin(pv_vals - peak_pv))

    # Calmar ratio (annualised return / |max drawdown %|)
    calmar = (ann_return / abs(max_dd_pct) * 100) if max_dd_pct != 0 else np.nan

    # VaR and CVaR at 95% confidence
    var_95  = -np.percentile(r, 5)
    cvar_95 = -r[r < -var_95].mean() if len(r[r < -var_95]) > 0 else var_95

    return {
        "label":       label,
        "T":           T,
        "mean_daily_return": mean_r,
        "std_daily_return":  std_r,
        "ann_return":        ann_return,
        "sharpe_ann":        sharpe_ann,
        "sortino_ann":       sortino,
        "max_dd_usd":        max_dd_usd,
        "max_dd_pct":        max_dd_pct,
        "calmar":            calmar,
        "var_95":            var_95,
        "cvar_95":           cvar_95,
        "final_pnl":         pnl[-1],
        "total_invested":    inv[-1],
        "return_on_invested": pnl[-1] / inv[-1] * 100 if inv[-1] > 0 else 0,
    }


# ── PRINT SECTIONS ────────────────────────────────────────────────────────────

def print_portfolio_overview(curve, mkt_pnl):
    section("SECTION 1 — PORTFOLIO OVERVIEW")
    print("""
  This section summarises the portfolio's current state.
  The strategy holds long positions across all Trump-related binary markets,
  betting on the pro-Trump outcome. All positions are unrealised (open).
""")
    last     = curve.iloc[-1]
    first_dt = curve["date"].min().strftime("%Y-%m-%d")
    last_dt  = curve["date"].max().strftime("%Y-%m-%d")
    n_days   = len(curve)

    print(f"  Period          : {first_dt} → {last_dt}  ({n_days} calendar days)")
    print(f"  Total invested  : {usd(last['invested'])}")
    print(f"  Portfolio value : {usd(last['portfolio_value'])}")
    print(f"  Unrealised P&L  : {usd(last['total_pnl'])}  ({last['total_pnl']/last['invested']*100:.2f}% of invested)")

    pos   = mkt_pnl[mkt_pnl["unrealised_pnl"] > 0]
    neg   = mkt_pnl[mkt_pnl["unrealised_pnl"] < 0]
    flat  = mkt_pnl[mkt_pnl["unrealised_pnl"] == 0]
    total = len(mkt_pnl)

    print(f"\n  Markets in portfolio : {total}")
    print(f"    Positive P&L       : {len(pos)}  ({len(pos)/total*100:.1f}%)")
    print(f"    Negative P&L       : {len(neg)}  ({len(neg)/total*100:.1f}%)")
    print(f"    Flat / no price    : {len(flat)}  ({len(flat)/total*100:.1f}%)")
    print(f"\n  YES bets             : {len(mkt_pnl[mkt_pnl['side']=='YES'])}")
    print(f"  NO bets (pro-Trump)  : {len(mkt_pnl[mkt_pnl['side']=='NO'])}")
    print("""
  Note: NO bets represent markets where the NO outcome is the pro-Trump
  position (e.g. "Will Trump be impeached?" → NO = Trump survives).
  These are valued at the NO price from Polymarket snapshots.
""")


def print_hypothesis_tests(curve_clean, curve_full,
                            ar_series, r_protrump, dr_sims,
                            mean_return_sims, pct_rank_mc):
    section("SECTION 2 — HYPOTHESIS TESTING")
    print(f"""
  We test whether the pro-Trump DCA strategy yields ABNORMAL RETURNS relative
  to a direction-neutral benchmark — isolating the political signal from general
  market friction (spreads, noise, liquidity effects).

  BENCHMARK: {len(mean_return_sims):,} Monte Carlo simulations of a 50/50 neutral strategy
  that places identical trades (same markets, dates, quantities) but randomly
  assigns YES or NO to each market with equal probability. This controls for
  everything except the political direction of the actual pro-Trump strategy.

  ABNORMAL RETURN: AR_t = R_proTrump_t − mean(R_neutral_t across simulations)

  H₀ : E[AR] = 0  (pro-Trump = neutral; no directional political signal)
  H₁a: E[AR] > 0  (pro-Trump outperforms neutral — market undervalues pro-Trump)
  H₁b: E[AR] < 0  (pro-Trump underperforms neutral — market overvalues pro-Trump,
                    consistent with crypto-bro buying inflating pro-Trump prices)

  Source: Brown & Warner (1985); MacKinlay (1997) — event-study framework
""")

    # 2a — Neutral benchmark summary
    subsection("2a — Neutral Benchmark Monte Carlo")
    mc_mean = float(mean_return_sims.mean())
    mc_std  = float(mean_return_sims.std())
    mc_p5   = float(np.percentile(mean_return_sims, 5))
    mc_p95  = float(np.percentile(mean_return_sims, 95))
    print(f"  Simulations        : {len(mean_return_sims):,}")
    print(f"  MC mean daily r    : {pct(mc_mean)}  (≈0 confirms neutrality)")
    print(f"  MC std             : {pct(mc_std)}")
    print(f"  MC 5th–95th pct    : [{pct(mc_p5)},  {pct(mc_p95)}]")
    print(f"\n  Pro-Trump mean r   : {pct(r_protrump.mean())}")
    print(f"  Percentile rank    : {pct_rank_mc:.1f}th  "
          f"(fraction of neutral sims with lower mean return)")
    if pct_rank_mc <= 5:
        print(f"  → Bottom 5% of neutral sims — strong evidence of systematic underperformance.")
    elif pct_rank_mc >= 95:
        print(f"  → Top 5% of neutral sims — strong evidence of systematic outperformance.")
    else:
        print(f"  → Within typical neutral-benchmark range (no strong directional signal).")

    # 2b — t-test on Abnormal Returns (PRIMARY)
    subsection("2b — t-Test on Abnormal Returns  [PRIMARY TEST]")
    print(f"  H₀: E[AR] = 0   H₁: E[AR] ≠ 0   (two-tailed, α = {ALPHA})\n")
    T_ar = len(ar_series)
    t_stat, p_val = stats.ttest_1samp(ar_series, popmean=0)
    se    = ar_series.std(ddof=1) / np.sqrt(T_ar)
    ci_lo = ar_series.mean() - 1.96 * se
    ci_hi = ar_series.mean() + 1.96 * se

    print(f"  N (days)           : {T_ar}")
    print(f"  Mean AR            : {pct(ar_series.mean())}")
    print(f"  Std AR             : {pct(ar_series.std(ddof=1))}")
    print(f"  t-statistic        : {t_stat:.4f}")
    print(f"  {fmt_p(p_val)}  {significance_stars(p_val)}")
    print(f"  95% CI on AR       : [{pct(ci_lo)},  {pct(ci_hi)}]")
    if p_val < ALPHA:
        direction = "POSITIVE (H₁a)" if ar_series.mean() > 0 else "NEGATIVE (H₁b)"
        print(f"\n  ✓ REJECT H₀ at α={ALPHA}  →  {direction} abnormal returns.")
        if ar_series.mean() < 0:
            print("    Pro-Trump underperforms the neutral benchmark — consistent with H₁b.")
            print("    Interpretation: ideologically motivated buyers inflate pro-Trump prices")
            print("    above their true probability, making the strategy systematically costly.")
        else:
            print("    Pro-Trump outperforms the neutral benchmark — consistent with H₁a.")
            print("    Interpretation: pro-Trump outcomes are systematically undervalued.")
    else:
        print(f"\n  ✗ FAIL TO REJECT H₀ (p = {p_val:.4f})")
        print("    Abnormal returns are not statistically distinguishable from zero.")
        print("    The political direction does not provide a measurable edge over")
        print("    a random-direction strategy on this dataset.")

    # 2c — Bootstrap BCa on AR
    subsection("2c — Bootstrap BCa CI on Abnormal Returns")
    print("  Method: scipy.stats.bootstrap, BCa, 10,000 resamples (Efron & Tibshirani 1993)\n")
    rng_bs = np.random.default_rng(42)
    bs_res = scipy_bootstrap((ar_series,), statistic=np.mean, n_resamples=10_000,
                              confidence_level=0.95, method="BCa", random_state=rng_bs)
    bca_lo, bca_hi = bs_res.confidence_interval.low, bs_res.confidence_interval.high
    print(f"  BCa 95% CI : [{pct(bca_lo)},  {pct(bca_hi)}]")
    if bca_lo > 0:
        print("  ✓ Entire CI above zero — bootstrap confirms positive abnormal returns.")
    elif bca_hi < 0:
        print("  ✓ Entire CI below zero — bootstrap confirms negative abnormal returns.")
    else:
        print("  ✗ CI straddles zero — bootstrap cannot confirm abnormal returns.")

    # 2d — Wilcoxon on AR
    subsection("2d — Wilcoxon Signed-Rank on Abnormal Returns")
    print("  Non-parametric median test on AR series (Wilcoxon 1945)\n")
    try:
        w_stat, w_p = stats.wilcoxon(ar_series, alternative="two-sided")
        print(f"  W = {w_stat:.1f},  {fmt_p(w_p)}  {significance_stars(w_p)}")
        if w_p < ALPHA:
            print(f"  ✓ REJECT H₀ — median AR significantly different from zero.")
        else:
            print(f"  ✗ FAIL TO REJECT H₀ — median AR not significantly different from zero.")
    except Exception as e:
        print(f"  Could not compute: {e}")

    # 2e — Non-parametric empirical p-value
    subsection("2e — Non-Parametric Percentile Test")
    print("  Empirical p-value: fraction of neutral sims achieving ≥ pro-Trump mean return.\n")
    emp_p_one  = float((mean_return_sims >= r_protrump.mean()).mean())
    emp_p_two  = min(emp_p_one, 1.0 - emp_p_one) * 2
    print(f"  P(neutral ≥ pro-Trump) : {emp_p_one:.4f}  (one-tailed; fraction of sims that beat pro-Trump)")
    print(f"  Two-tailed equiv.      : {emp_p_two:.4f}  {significance_stars(emp_p_two)}")
    if emp_p_one >= 1 - ALPHA:
        # Almost all neutral sims beat pro-Trump → pro-Trump is in the lower tail
        print(f"  ✓ Pro-Trump significantly UNDERPERFORMS neutral benchmark at α={ALPHA}.")
        print(f"    {emp_p_one*100:.1f}% of random-direction portfolios achieve higher mean returns.")
        print("    Consistent with H₁b: pro-Trump direction destroys value vs neutral chance.")
    elif emp_p_one <= ALPHA:
        # Very few neutral sims beat pro-Trump → pro-Trump is in the upper tail
        print(f"  ✓ Pro-Trump significantly OUTPERFORMS neutral benchmark at α={ALPHA}.")
        print("    Consistent with H₁a: pro-Trump direction adds value vs neutral chance.")
    else:
        print(f"  ✗ No significant directional deviation from the neutral benchmark.")

    # 2f — OLS trend (robustness)
    subsection("2f — OLS Trend on Pro-Trump Equity Curve  [Robustness]")
    print("  Model: total_pnl_t = α + β·t + ε_t  (HC3 robust SE, Wooldridge 2012)\n")
    for curve, label in [(curve_clean, "CLEAN SERIES"), (curve_full, "FULL SERIES")]:
        clean_df = curve.dropna(subset=["total_pnl"])
        t_idx = np.arange(len(clean_df))
        y = clean_df["total_pnl"].values
        X = sm.add_constant(t_idx)
        model = sm.OLS(y, X).fit(cov_type="HC3")
        beta, beta_p, r2 = model.params[1], model.pvalues[1], model.rsquared
        print(f"  [{label}]  β = {beta:.4f} $/day  ({beta*365:.2f} $/yr)  "
              f"R² = {r2:.4f}  {fmt_p(beta_p)}  {significance_stars(beta_p)}")

    # 2g — Raw μ=0 t-test (secondary reference)
    subsection("2g — Raw Return t-Test vs Zero  [Secondary]")
    print("  Tests H₀: μ=0 directly on pro-Trump raw returns (no benchmark comparison).\n")
    for curve, label in [(curve_clean, "CLEAN"), (curve_full, "FULL")]:
        r = curve["daily_return"].dropna().values
        t_s, p_v = stats.ttest_1samp(r, popmean=0)
        print(f"  [{label:5s}]  N={len(r):3d}  mean={pct(r.mean())}  "
              f"t={t_s:.4f}  {fmt_p(p_v)}  {significance_stars(p_v)}")
    print()


def print_risk_metrics(metrics):
    section("SECTION 3 — RISK-ADJUSTED PERFORMANCE METRICS")
    print("""
  These metrics contextualise the strategy's return relative to its risk.
  All ratios are annualised using √365 (prediction markets operate 365 days/year,
  unlike equity markets which use √252).
""")
    m = metrics
    subsection("3a — Sharpe Ratio")
    print("""  Formula : Sharpe = (mean daily return / std daily return) × √365
  Source  : Sharpe (1966, 1994)
  Meaning : Return per unit of total risk. Sharpe > 1.0 is considered good;
            negative Sharpe means the strategy loses money on a risk-adjusted basis.
""")
    print(f"  Daily Sharpe (non-annualised) : {m['mean_daily_return']/m['std_daily_return']:.4f}")
    print(f"  Annualised Sharpe             : {m['sharpe_ann']:.4f}")

    subsection("3b — Sortino Ratio")
    print("""  Formula : Sortino = (mean daily return / downside deviation) × √365
  Source  : Sortino & van der Meer (1991)
  Meaning : Like Sharpe, but only penalises downside volatility (losses),
            not upside volatility (gains). More appropriate for asymmetric
            return distributions like prediction market payoffs.
""")
    print(f"  Annualised Sortino : {m['sortino_ann']:.4f}")

    subsection("3c — Maximum Drawdown & Calmar Ratio")
    print("""  Source: Young (1991) — Calmar; Magdon-Ismail & Atiya (2004) — drawdown
  Maximum drawdown: largest peak-to-trough decline in cumulative P&L.
  Calmar ratio:     annualised return / |max drawdown %| — risk-return trade-off.
""")
    print(f"  Max drawdown (USD) : {usd(m['max_dd_usd'])}")
    print(f"  Max drawdown (%)   : {m['max_dd_pct']:.2f}%  (relative to portfolio peak)")
    print(f"  Calmar ratio       : {m['calmar']:.4f}" if not np.isnan(m['calmar']) else "  Calmar ratio : N/A")

    subsection("3d — Value at Risk (VaR) and Conditional VaR (CVaR)")
    print("""  Source: Jorion (2006) — VaR; Rockafellar & Uryasev (2000) — CVaR
  VaR 95%  : The daily loss we expect to exceed only 5% of the time.
  CVaR 95% : The average loss on the worst 5% of days (expected shortfall).
             CVaR is a "coherent" risk measure (Artzner et al. 1999) and
             better captures tail risk than VaR alone.
""")
    print(f"  VaR  95% (daily) : {pct(m['var_95'])}  of invested capital")
    print(f"  CVaR 95% (daily) : {pct(m['cvar_95'])}  of invested capital")

    subsection("3e — Overall Return Summary")
    print(f"  Total invested        : {usd(m['total_invested'])}")
    print(f"  Final unrealised P&L  : {usd(m['final_pnl'])}")
    print(f"  Return on invested    : {m['return_on_invested']:.2f}%")
    print(f"  Annualised return     : {m['ann_return']*100:.2f}%")
    print()


def print_diagnostics_summary(curve):
    section("SECTION 4 — RETURN DISTRIBUTION DIAGNOSTICS")
    print("""
  Before interpreting the hypothesis tests, we verify the statistical
  assumptions underlying them. This section reports the diagnostic tests
  that were run prior to the formal analysis.
""")
    r  = curve["daily_return"].dropna().values
    T  = len(r)

    subsection("4a — Descriptive Statistics")
    print(f"  N (observations)   : {T}")
    print(f"  Mean daily return  : {pct(r.mean())}")
    print(f"  Std deviation      : {pct(r.std(ddof=1))}")
    print(f"  Skewness           : {stats.skew(r):.4f}  (0 = symmetric; negative = left tail)")
    print(f"  Excess kurtosis    : {stats.kurtosis(r):.4f}  (0 = normal; positive = fat tails)")
    print(f"  Min daily return   : {pct(r.min())}")
    print(f"  Max daily return   : {pct(r.max())}")

    subsection("4b — Normality Tests")
    print("  Source: Shapiro & Wilk (1965); Jarque & Bera (1987)")
    sw_stat, sw_p = stats.shapiro(r)
    jb = stats.jarque_bera(r)
    jb_stat, jb_p = jb.statistic, jb.pvalue
    print(f"  Shapiro-Wilk  W={sw_stat:.4f},  {fmt_p(sw_p)}  {significance_stars(sw_p)}")
    print(f"  Jarque-Bera   JB={jb_stat:.4f}, {fmt_p(jb_p)}  {significance_stars(jb_p)}")
    norm_rejected = sw_p < ALPHA or jb_p < ALPHA
    print(f"\n  → {'Normality rejected — Bootstrap BCa CI and Wilcoxon test provide' if norm_rejected else 'Normality cannot be rejected —'}")
    if norm_rejected:
        print("    assumption-free robustness checks (reported in Section 2b & 2c).")
    else:
        print("    t-test distributional assumption is satisfied.")

    subsection("4c — Serial Independence (Ljung-Box Q-Test)")
    print("  Source: Ljung & Box (1978)")
    print("  Tests whether return autocorrelations at lags 1–10 are jointly zero.")
    print("  If rejected: returns are predictable from their own history (trend/momentum).\n")
    lags  = [l for l in [1, 5, 10] if l <= T // 5]
    lb    = acorr_ljungbox(r, lags=lags, return_df=True)
    ac_flag = False
    for lag in lags:
        row = lb.loc[lag]
        flag = "← AUTOCORRELATION" if row["lb_pvalue"] < ALPHA else ""
        print(f"  Lag {lag:2d}: Q={row['lb_stat']:.4f},  {fmt_p(row['lb_pvalue'])}  {significance_stars(row['lb_pvalue'])}  {flag}")
        if row["lb_pvalue"] < ALPHA:
            ac_flag = True
    dw = durbin_watson(r)
    print(f"\n  Durbin-Watson : {dw:.4f}  (2.0 = no autocorrelation)")
    print(f"\n  → {'No significant lag-1 autocorrelation — standard t-test is valid.' if not ac_flag else 'Autocorrelation detected — interpret t-test with caution.'}")

    subsection("4d — Stationarity (Augmented Dickey-Fuller Test)")
    print("  Source: Said & Dickey (1984)")
    print("  Tests whether the return series has a unit root (non-stationary trend).")
    print("  Stationarity is required for valid t-test inference.\n")
    adf_stat, adf_p, adf_lags, _, adf_cv, _ = adfuller(r, autolag="AIC")
    print(f"  ADF statistic   : {adf_stat:.4f}")
    print(f"  {fmt_p(adf_p)}")
    print(f"  Lags used       : {adf_lags}")
    print(f"  Critical values : 1% = {adf_cv['1%']:.3f},  5% = {adf_cv['5%']:.3f},  10% = {adf_cv['10%']:.3f}")
    print(f"\n  → {'Return series is STATIONARY — t-test inference is valid.' if adf_p < ALPHA else 'Non-stationarity cannot be ruled out.'}")
    print()


def print_per_market(mkt_pnl):
    section("SECTION 5 — CROSS-SECTIONAL MARKET ANALYSIS")
    print("""
  Decomposing portfolio P&L by individual market reveals whether returns are
  concentrated in a few markets (idiosyncratic) or spread portfolio-wide
  (systematic). Systematic losses across most markets would be consistent
  with H₁b (broad overvaluation of pro-Trump outcomes), while concentration
  in a few large losers might reflect market-specific factors.
""")
    total_pnl = mkt_pnl["unrealised_pnl"].sum()
    pos   = mkt_pnl[mkt_pnl["unrealised_pnl"] > 0]
    neg   = mkt_pnl[mkt_pnl["unrealised_pnl"] < 0]
    print(f"  Total markets analysed   : {len(mkt_pnl)}")
    print(f"  Markets with gain        : {len(pos)}  (sum = {usd(pos['unrealised_pnl'].sum())})")
    print(f"  Markets with loss        : {len(neg)}  (sum = {usd(neg['unrealised_pnl'].sum())})")
    print(f"  Portfolio total P&L      : {usd(total_pnl)}")
    if len(neg) > 0:
        pf = pos["unrealised_pnl"].sum() / abs(neg["unrealised_pnl"].sum())
        print(f"  Profit factor            : {pf:.4f}  (gross gain / gross loss; >1 = net positive)")
    print(f"  Win rate (% of markets)  : {len(pos)/len(mkt_pnl)*100:.1f}%")

    print("\n  Top 5 winning markets:")
    for row in mkt_pnl.nlargest(5, "unrealised_pnl").itertuples():
        print(f"    {row.market_id[:20]:20s}  {row.side:3s}  entry={row.avg_entry:.3f}  "
              f"now={row.current_price:.3f}  P&L={usd(row.unrealised_pnl)}")
    print("\n  Top 5 losing markets:")
    for row in mkt_pnl.nsmallest(5, "unrealised_pnl").itertuples():
        print(f"    {row.market_id[:20]:20s}  {row.side:3s}  entry={row.avg_entry:.3f}  "
              f"now={row.current_price:.3f}  P&L={usd(row.unrealised_pnl)}")
    print()


# ── FIGURES ───────────────────────────────────────────────────────────────────

def style_ax(ax, title, xlabel, ylabel):
    ax.set_title(title, fontsize=11, fontweight="bold", pad=10, color=C_TEXT)
    ax.set_xlabel(xlabel, fontsize=9, color=C_TEXT)
    ax.set_ylabel(ylabel, fontsize=9, color=C_TEXT)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(C_GRID)
    ax.spines["bottom"].set_color(C_GRID)
    ax.tick_params(colors=C_TEXT, labelsize=8)
    ax.grid(True, color=C_GRID, linewidth=0.6, linestyle="--")
    ax.set_facecolor("white")


def save_fig(fig, name):
    path = FIGURES_DIR / name
    fig.savefig(path, dpi=FIGURE_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  Saved: {path.name}")


def fig1_equity_curve(curve, prosp_start=None):
    """Fig 1: Portfolio value vs invested capital — full timeline with period divider."""
    fig, ax = plt.subplots(figsize=(13, 5))
    dates = curve["date"]
    pv    = curve["portfolio_value"]
    inv   = curve["invested"]

    ax.fill_between(dates, pv, inv, where=(pv >= inv), alpha=0.25, color=C_GAIN, label="_gain area")
    ax.fill_between(dates, pv, inv, where=(pv <  inv), alpha=0.25, color=C_LOSS, label="_loss area")
    ax.plot(dates, inv, color=C_INV, linewidth=1.5, linestyle="--", label="Cumulative invested (cost basis)")
    ax.plot(dates, pv,  color=C_PRO, linewidth=2.0, label="Portfolio value (mark-to-market)")

    # Period divider
    if prosp_start is not None:
        pd_dt = pd.to_datetime(prosp_start)
        ax.axvline(x=pd_dt, color=C_TEXT, linewidth=1.2, linestyle=":", alpha=0.7)
        y_top = ax.get_ylim()[1]
        ax.text(pd_dt, y_top * 0.97, "  Prospective →", fontsize=8, color=C_TEXT, va="top")
        ax.text(pd_dt, y_top * 0.97, "← Retrospective  ", fontsize=8, color=C_TEXT, va="top", ha="right")

    ax.axhline(y=0, color=C_GRID, linewidth=0.8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))

    ax.legend(loc="upper left", fontsize=8, framealpha=0.9)
    start_yr = curve["date"].min().strftime("%b %Y")
    end_yr   = curve["date"].max().strftime("%b %Y")
    style_ax(ax,
        title=f"Figure 1 — Portfolio Value vs Invested Capital\n"
              f"Pro-Trump DCA Strategy (Polymarket, {start_yr} – {end_yr})",
        xlabel="Date", ylabel="USD")
    fig.tight_layout()
    save_fig(fig, "fig1_equity_curve.png")


def fig2_daily_pnl(curve):
    """Fig 2: Daily P&L changes as a bar chart."""
    df = curve.dropna(subset=["daily_pnl_change"]).copy()
    fig, ax = plt.subplots(figsize=(11, 4))
    colors = [C_GAIN if v >= 0 else C_LOSS for v in df["daily_pnl_change"]]
    ax.bar(df["date"], df["daily_pnl_change"], color=colors, width=0.8, alpha=0.85)
    ax.axhline(y=0, color=C_TEXT, linewidth=0.8)
    mean_chg = df["daily_pnl_change"].mean()
    ax.axhline(y=mean_chg, color=C_PRO, linewidth=1.2, linestyle="--",
               label=f"Mean daily change = ${mean_chg:.2f}")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.1f}"))
    ax.legend(fontsize=8)
    style_ax(ax,
        title="Figure 2 — Daily P&L Changes\nGreen = portfolio gained value; Red = portfolio lost value",
        xlabel="Date", ylabel="Daily P&L change (USD)")
    fig.tight_layout()
    save_fig(fig, "fig2_daily_pnl.png")


def fig3_return_distribution(curve):
    """Fig 3: Return histogram + KDE + normal overlay."""
    r   = curve["daily_return"].dropna().values
    fig, ax = plt.subplots(figsize=(8, 5))

    n, bins, _ = ax.hist(r * 100, bins=25, color=C_PRO, alpha=0.55,
                          edgecolor="white", linewidth=0.5, density=True, label="Observed returns")

    # KDE
    from scipy.stats import gaussian_kde
    kde    = gaussian_kde(r * 100, bw_method="scott")
    x_vals = np.linspace(r.min() * 100 - 0.5, r.max() * 100 + 0.5, 300)
    ax.plot(x_vals, kde(x_vals), color=C_PRO, linewidth=2.0, label="KDE")

    # Normal overlay
    mu, sigma = r.mean() * 100, r.std(ddof=1) * 100
    norm_vals  = stats.norm.pdf(x_vals, mu, sigma)
    ax.plot(x_vals, norm_vals, color=C_LOSS, linewidth=1.8, linestyle="--",
            label=f"Normal fit (μ={mu:.3f}%, σ={sigma:.3f}%)")

    ax.axvline(x=0,  color=C_TEXT, linewidth=1.0, linestyle=":", alpha=0.7, label="Zero return")
    ax.axvline(x=mu, color=C_GAIN, linewidth=1.2, linestyle="--",
               label=f"Mean = {mu:.4f}%")

    # Annotations
    jb  = stats.jarque_bera(r)
    sw_stat, sw_p = stats.shapiro(r)
    ax.text(0.97, 0.95,
            f"Skewness = {stats.skew(r):.3f}\n"
            f"Ex. kurtosis = {stats.kurtosis(r):.3f}\n"
            f"Jarque-Bera p = {jb.pvalue:.4f}\n"
            f"Shapiro-Wilk p = {sw_p:.4f}",
            transform=ax.transAxes, va="top", ha="right",
            fontsize=8, bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))

    ax.legend(fontsize=8)
    style_ax(ax,
        title="Figure 3 — Distribution of Daily Returns\n"
              "With KDE and normal distribution overlay",
        xlabel="Daily return (%)", ylabel="Density")
    fig.tight_layout()
    save_fig(fig, "fig3_return_distribution.png")


def fig4_qq_plot(curve):
    """Fig 4: Q-Q plot vs standard normal."""
    r   = curve["daily_return"].dropna().values
    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    (osm, osr), (slope, intercept, _) = probplot(r, dist="norm", plot=None)
    ax.scatter(osm, osr, color=C_PRO, s=18, alpha=0.75, label="Observed quantiles")
    fit_line = slope * np.array([osm.min(), osm.max()]) + intercept
    ax.plot([osm.min(), osm.max()], fit_line, color=C_LOSS, linewidth=1.5,
            linestyle="--", label="Theoretical normal line")
    ax.legend(fontsize=8)
    style_ax(ax,
        title="Figure 4 — Q-Q Plot (Daily Returns vs Normal Distribution)\n"
              "Points on the line indicate normality",
        xlabel="Theoretical quantiles", ylabel="Sample quantiles")
    fig.tight_layout()
    save_fig(fig, "fig4_qq_plot.png")


def fig5_acf_pacf(curve):
    """Fig 5: ACF and PACF of daily returns."""
    from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
    r   = curve["daily_return"].dropna().values
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4))
    plot_acf(r,  ax=ax1, lags=20, color=C_PRO, title="", zero=False)
    plot_pacf(r, ax=ax2, lags=20, color=C_PRO, title="", zero=False, method="ywm")
    style_ax(ax1,
        title="Figure 5a — Autocorrelation Function (ACF)\n"
              "Blue region = 95% confidence band (no autocorrelation)",
        xlabel="Lag (days)", ylabel="Autocorrelation")
    style_ax(ax2,
        title="Figure 5b — Partial Autocorrelation Function (PACF)\n"
              "Significant spikes indicate serial dependence",
        xlabel="Lag (days)", ylabel="Partial autocorrelation")
    fig.tight_layout()
    save_fig(fig, "fig5_acf_pacf.png")


def fig6_drawdown(curve):
    """Fig 6: Running drawdown from portfolio value peak."""
    fig, ax = plt.subplots(figsize=(11, 4))
    dd = curve["drawdown_pct"].values
    ax.fill_between(curve["date"], dd, 0, color=C_LOSS, alpha=0.55, label="Drawdown")
    ax.plot(curve["date"], dd, color=C_LOSS, linewidth=1.2)
    ax.axhline(y=0, color=C_TEXT, linewidth=0.8)
    max_dd = dd.min()
    max_dd_date = curve["date"].iloc[dd.argmin()]
    ax.annotate(f"Max drawdown\n{max_dd:.2f}%",
                xy=(max_dd_date, max_dd),
                xytext=(max_dd_date, max_dd - 3),
                fontsize=8, color=C_LOSS,
                arrowprops=dict(arrowstyle="->", color=C_LOSS))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.1f}%"))
    style_ax(ax,
        title="Figure 6 — Portfolio Drawdown\nPeak-to-trough decline in portfolio value (%)",
        xlabel="Date", ylabel="Drawdown (%)")
    fig.tight_layout()
    save_fig(fig, "fig6_drawdown.png")


def fig7_market_pnl(mkt_pnl, top_n=20):
    """Fig 7: Top/bottom markets by unrealised P&L."""
    top  = mkt_pnl.nlargest(top_n,  "unrealised_pnl")
    bot  = mkt_pnl.nsmallest(top_n, "unrealised_pnl")
    combined = pd.concat([bot, top]).drop_duplicates("market_id")
    combined = combined.sort_values("unrealised_pnl")

    fig, ax = plt.subplots(figsize=(9, max(6, len(combined) * 0.28)))
    colors  = [C_GAIN if v >= 0 else C_LOSS for v in combined["unrealised_pnl"]]
    labels  = [f"{row.market_id[:28]}  ({row.side})" for row in combined.itertuples()]
    ax.barh(labels, combined["unrealised_pnl"], color=colors, alpha=0.85, edgecolor="white", height=0.7)
    ax.axvline(x=0, color=C_TEXT, linewidth=0.9)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.1f}"))
    style_ax(ax,
        title=f"Figure 7 — Per-Market Unrealised P&L (Top/Bottom {top_n})\n"
              "Green = market is profitable; Red = market is losing",
        xlabel="Unrealised P&L (USD)", ylabel="Market ID (side)")
    ax.tick_params(axis="y", labelsize=7)
    fig.tight_layout()
    save_fig(fig, "fig7_market_pnl.png")


def fig8_mc_equity_comparison(curve_full, pnl_sims_mc, date_range_mc, prosp_start=None):
    """Fig 8: Pro-Trump cumulative P&L vs neutral benchmark fan (median + 5–95% band)."""
    T_mc  = pnl_sims_mc.shape[1]
    x_mc  = pd.to_datetime(list(date_range_mc)[:T_mc])

    p5_mc  = np.nanpercentile(pnl_sims_mc, 5,  axis=0)
    p25_mc = np.nanpercentile(pnl_sims_mc, 25, axis=0)
    p50_mc = np.nanpercentile(pnl_sims_mc, 50, axis=0)
    p75_mc = np.nanpercentile(pnl_sims_mc, 75, axis=0)
    p95_mc = np.nanpercentile(pnl_sims_mc, 95, axis=0)

    fig, ax = plt.subplots(figsize=(13, 5))

    # Neutral MC fan
    ax.fill_between(x_mc, p5_mc,  p95_mc, color="#94a3b8", alpha=0.15, label="Neutral 5–95th pct")
    ax.fill_between(x_mc, p25_mc, p75_mc, color="#94a3b8", alpha=0.28, label="Neutral 25–75th pct")
    ax.plot(x_mc, p50_mc, color="#94a3b8", linewidth=1.5, linestyle="--", label="Neutral median")

    # Pro-Trump actual
    ax.plot(curve_full["date"], curve_full["total_pnl"],
            color=C_PRO, linewidth=2.2, label="Pro-Trump (actual)")

    # Zero line
    ax.axhline(y=0, color=C_TEXT, linewidth=0.8, linestyle=":")

    # Prospective divider
    if prosp_start:
        ax.axvline(pd.to_datetime(prosp_start), color="#64748b",
                   linewidth=1.0, linestyle="--", alpha=0.7)
        ax.text(pd.to_datetime(prosp_start), ax.get_ylim()[1] * 0.92,
                " Live →", fontsize=8, color="#64748b", va="top")

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax.legend(fontsize=8, loc="upper left")
    style_ax(ax,
             title="Figure 8 — Cumulative P&L: Pro-Trump vs Neutral Benchmark\n"
                   "Shaded bands = 10,000 random-direction simulations",
             xlabel="Date", ylabel="Cumulative P&L (USD)")
    fig.tight_layout()
    save_fig(fig, "fig8_mc_equity_comparison.png")


def fig9_rolling_sharpe(curve, window=20):
    """Fig 9: Rolling Sharpe ratio (annualised)."""
    r    = curve["daily_return"]
    roll = r.rolling(window)
    rolling_sharpe = (roll.mean() / roll.std(ddof=1)) * np.sqrt(365)

    fig, ax = plt.subplots(figsize=(11, 4))
    ax.fill_between(curve["date"], rolling_sharpe, 0,
                    where=(rolling_sharpe >= 0), alpha=0.3, color=C_GAIN)
    ax.fill_between(curve["date"], rolling_sharpe, 0,
                    where=(rolling_sharpe < 0),  alpha=0.3, color=C_LOSS)
    ax.plot(curve["date"], rolling_sharpe, color=C_PRO, linewidth=1.8,
            label=f"{window}-day rolling Sharpe (annualised)")
    ax.axhline(y=0,   color=C_TEXT, linewidth=0.8, linestyle=":")
    ax.axhline(y=1.0, color=C_GAIN, linewidth=0.8, linestyle="--", alpha=0.6, label="Sharpe = 1.0 (benchmark)")
    ax.axhline(y=-1.0,color=C_LOSS, linewidth=0.8, linestyle="--", alpha=0.6)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right")
    ax.legend(fontsize=8)
    style_ax(ax,
        title=f"Figure 9 — Rolling {window}-Day Sharpe Ratio (Annualised)\n"
              "Positive = strategy is generating risk-adjusted gains in that window",
        xlabel="Date", ylabel="Sharpe ratio (annualised)")
    fig.tight_layout()
    save_fig(fig, "fig9_rolling_sharpe.png")


# ── SECTION 9 — RETROSPECTIVE vs PROSPECTIVE ─────────────────────────────────

def _run_ttest_block(r, label):
    """Run t-test + bootstrap BCa + Wilcoxon and return a result dict."""
    T = len(r)
    if T < 3:
        return {"label": label, "T": T, "error": "insufficient observations"}

    t_stat, p_val = stats.ttest_1samp(r, popmean=0)
    se  = r.std(ddof=1) / np.sqrt(T)
    ci_lo, ci_hi = r.mean() - 1.96 * se, r.mean() + 1.96 * se

    rng    = np.random.default_rng(42)
    bs_res = scipy_bootstrap((r,), statistic=np.mean, n_resamples=10_000,
                              confidence_level=0.95, method="BCa", random_state=rng)

    try:
        w_stat, w_p = stats.wilcoxon(r, alternative="two-sided")
    except Exception:
        w_stat, w_p = np.nan, np.nan

    return {
        "label":    label,
        "T":        T,
        "mean_r":   r.mean(),
        "std_r":    r.std(ddof=1),
        "t_stat":   t_stat,
        "p_val":    p_val,
        "ci_lo":    ci_lo,
        "ci_hi":    ci_hi,
        "bca_lo":   bs_res.confidence_interval.low,
        "bca_hi":   bs_res.confidence_interval.high,
        "w_stat":   w_stat,
        "w_p":      w_p,
    }


def _print_ttest_block(res):
    if "error" in res:
        print(f"  [{res['label']}]  Skipped — {res['error']}")
        return
    r   = res
    sig = significance_stars(r["p_val"])
    print(f"  ┌─ {r['label']}")
    print(f"  │  N = {r['T']}  |  mean = {pct(r['mean_r'])}  |  std = {pct(r['std_r'])}")
    print(f"  │  t = {r['t_stat']:.4f},  {fmt_p(r['p_val'])}  {sig}")
    print(f"  │  95% CI  : [{pct(r['ci_lo'])},  {pct(r['ci_hi'])}]")
    print(f"  │  BCa CI  : [{pct(r['bca_lo'])},  {pct(r['bca_hi'])}]")
    print(f"  └  Wilcoxon: W={r['w_stat']:.1f},  {fmt_p(r['w_p'])}  {significance_stars(r['w_p'])}")
    print()


def print_retro_prosp_comparison(curve_retro, curve_prosp_full, curve_prosp_clean):
    section("SECTION 9 — RETROSPECTIVE vs PROSPECTIVE COMPARISON")
    print(f"""
  Following the professor's suggestion, the full dataset is split at the
  date live collection began ({PROSPECTIVE_START}):

    • RETROSPECTIVE  — CLOB historical prices before {PROSPECTIVE_START}
      Markets existed and were already trading; prices obtained post-hoc
      from Polymarket's CLOB API. Represents a simulated back-test.

    • PROSPECTIVE    — Live collection from {PROSPECTIVE_START} onward
      Prices collected in real time using the Gamma API.
      Represents a genuine forward test (no look-ahead bias).

  If both periods show the same direction and significance, this is strong
  evidence that the effect is structural (not a one-period artefact).
  If they diverge, it signals that the bias may have changed over time.
""")

    retro_r  = curve_retro["daily_return"].dropna().values
    prosp_r  = curve_prosp_full["daily_return"].dropna().values
    clean_r  = curve_prosp_clean["daily_return"].dropna().values

    res_retro  = _run_ttest_block(retro_r,  f"RETROSPECTIVE  (before {PROSPECTIVE_START})")
    res_prosp  = _run_ttest_block(prosp_r,  f"PROSPECTIVE — full  ({PROSPECTIVE_START} → present)")
    res_clean  = _run_ttest_block(clean_r,  f"PROSPECTIVE — clean ({CLEAN_START} → present)")

    subsection("9a — Hypothesis Tests by Period")
    print("  Method: One-sample t-test, Bootstrap BCa CI, Wilcoxon signed-rank\n")
    _print_ttest_block(res_retro)
    _print_ttest_block(res_prosp)
    _print_ttest_block(res_clean)

    # Cross-period consistency
    subsection("9b — Cross-Period Consistency")
    def direction(res):
        if res.get("error"):
            return "unknown"
        return "positive" if res["mean_r"] > 0 else "negative"

    def sig(res):
        if res.get("error"):
            return False
        return res["p_val"] < ALPHA

    d_retro = direction(res_retro)
    d_prosp = direction(res_clean)
    s_retro = sig(res_retro)
    s_prosp = sig(res_clean)

    print(f"  Retrospective direction : {d_retro}  ({'significant' if s_retro else 'not significant'} at α={ALPHA})")
    print(f"  Prospective   direction : {d_prosp}  ({'significant' if s_prosp else 'not significant'} at α={ALPHA})")
    print()

    if d_retro == d_prosp:
        consistent = True
        print(f"  ✓ Both periods show {d_retro} mean returns — directions are CONSISTENT.")
        if s_retro and s_prosp:
            print("  ✓ Both periods are statistically significant — strong evidence of a")
            print(f"    structural {d_retro} bias across the full observation window.")
            if d_retro == "negative":
                print("    Consistent with H₁b: pro-Trump outcomes systematically overvalued.")
            else:
                print("    Consistent with H₁a: pro-Trump outcomes systematically undervalued.")
        elif s_retro or s_prosp:
            which = "retrospective" if s_retro else "prospective"
            print(f"  ~  Only the {which} period is significant — the pattern is present but")
            print("     may not persist across all sub-periods. Report with caution.")
        else:
            print("  ~  Neither period is individually significant, though both point the")
            print("     same direction. The combined full-series test provides more power.")
    else:
        consistent = False
        print(f"  ✗ Periods DISAGREE: retrospective = {d_retro}, prospective = {d_prosp}.")
        print("    The strategy's performance may have changed over time, or the")
        print("    retrospective period contains structural differences from the")
        print("    prospective period (different market composition, political context).")

    # P&L summary table
    subsection("9c — Period P&L Summary")
    retro_last = curve_retro.iloc[-1]
    prosp_last = curve_prosp_full.iloc[-1]
    print(f"  {'Period':<35}  {'Days':>5}  {'Final P&L':>12}  {'Invested':>12}  {'Return':>8}")
    print(f"  {'─'*35}  {'─'*5}  {'─'*12}  {'─'*12}  {'─'*8}")
    def _row(label, curve):
        last = curve.iloc[-1]
        inv  = last["invested"]
        ret  = last["total_pnl"] / inv * 100 if inv > 0 else 0
        print(f"  {label:<35}  {len(curve):>5}  {usd(last['total_pnl']):>12}  {usd(inv):>12}  {ret:>7.2f}%")
    _row(f"Retrospective (before {PROSPECTIVE_START})", curve_retro)
    _row(f"Prospective — full ({PROSPECTIVE_START}+)", curve_prosp_full)
    _row(f"Prospective — clean ({CLEAN_START}+)",      curve_prosp_clean)
    print()


def fig10_retro_vs_prosp(curve_retro, curve_prosp):
    """Fig 10: Retrospective vs prospective equity curves side-by-side."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    for ax, curve, title_period, color_period in [
        (axes[0], curve_retro,  "Retrospective (CLOB historical)", C_INV),
        (axes[1], curve_prosp,  "Prospective (live collection)",   C_PRO),
    ]:
        dates = curve["date"]
        pv    = curve["portfolio_value"]
        inv   = curve["invested"]

        ax.fill_between(dates, pv, inv, where=(pv >= inv), alpha=0.2, color=C_GAIN)
        ax.fill_between(dates, pv, inv, where=(pv <  inv), alpha=0.2, color=C_LOSS)
        ax.plot(dates, inv, color=C_INV,          linewidth=1.4, linestyle="--", label="Invested")
        ax.plot(dates, pv,  color=color_period,   linewidth=2.0, label="Portfolio value")
        ax.axhline(y=0, color=C_GRID, linewidth=0.7)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right")
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
        ax.legend(fontsize=8)
        style_ax(ax, title=f"Figure 10 — {title_period}", xlabel="Date", ylabel="USD")

    fig.suptitle("Figure 10 — Retrospective vs Prospective Portfolio Performance",
                 fontsize=12, fontweight="bold", y=1.02)
    fig.tight_layout()
    save_fig(fig, "fig10_retro_vs_prosp.png")


def fig11_mc_benchmark(mean_return_sims, dr_sims, r_protrump, date_range_mc, pct_rank_mc):
    """Fig 11: Neutral MC benchmark — histogram of simulation means + daily fan chart."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Panel A — histogram of MC mean returns
    vals     = mean_return_sims * 100
    pro_mean = float(r_protrump.mean() * 100)

    n, bin_edges, _ = ax1.hist(vals, bins=60, color="#94a3b8", alpha=0.75,
                                edgecolor="white", linewidth=0.3,
                                label=f"Neutral benchmark ({len(vals):,} sims)")
    # Re-shade the tail more extreme than pro-Trump
    lo_mask = vals <= pro_mean
    ax1.hist(vals[lo_mask], bins=bin_edges, color=C_LOSS, alpha=0.55,
             edgecolor="white", linewidth=0.3, label="Below pro-Trump")
    ax1.axvline(x=pro_mean, color=C_PRO, linewidth=2.2, linestyle="--",
                label=f"Pro-Trump mean: {pro_mean:.4f}%")
    y_top = ax1.get_ylim()[1]
    ax1.text(pro_mean + (bin_edges[-1] - bin_edges[0]) * 0.01, y_top * 0.92,
             f"{pct_rank_mc:.1f}th\npercentile", fontsize=8.5, color=C_PRO, va="top")
    ax1.legend(fontsize=8)
    style_ax(ax1,
        title="Figure 11a — Neutral Benchmark Distribution\n"
              "10,000 random-direction simulations vs actual pro-Trump strategy",
        xlabel="Mean daily return (%)", ylabel="Count")

    # Panel B — fan chart of daily returns over time
    T = dr_sims.shape[1]
    dates_arr = list(date_range_mc)[1:T + 1]
    x = pd.to_datetime(dates_arr)

    p5  = np.nanpercentile(dr_sims, 5,  axis=0) * 100
    p25 = np.nanpercentile(dr_sims, 25, axis=0) * 100
    p50 = np.nanpercentile(dr_sims, 50, axis=0) * 100
    p75 = np.nanpercentile(dr_sims, 75, axis=0) * 100
    p95 = np.nanpercentile(dr_sims, 95, axis=0) * 100

    ax2.fill_between(x, p5,  p95, color="#94a3b8", alpha=0.20, label="MC 5–95%")
    ax2.fill_between(x, p25, p75, color="#94a3b8", alpha=0.40, label="MC 25–75%")
    ax2.plot(x, p50, color="#64748b", linewidth=1.2, linestyle="--", label="MC median")

    # Align pro-Trump series to the same x axis (tail T values)
    ax2.plot(x[-len(r_protrump):], r_protrump * 100,
             color=C_PRO, linewidth=1.8, label="Pro-Trump actual")
    ax2.axhline(y=0, color=C_TEXT, linewidth=0.6, linestyle=":")
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax2.xaxis.set_major_locator(mdates.MonthLocator())
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=30, ha="right")
    ax2.legend(fontsize=8)
    style_ax(ax2,
        title="Figure 11b — Daily Returns: Pro-Trump vs Neutral Fan Chart",
        xlabel="Date", ylabel="Daily return (%)")

    fig.tight_layout()
    save_fig(fig, "fig11_mc_benchmark.png")


# ── EXPORT ────────────────────────────────────────────────────────────────────

def export_results(curve_clean, curve_full, mkt_pnl, metrics, output_dir,
                   mean_return_sims=None, ar_series=None,
                   r_protrump=None, r_neutral_mean=None,
                   pct_rank_mc=None):
    # Equity curves
    curve_clean.to_csv(output_dir / "equity_curve_clean.csv", index=False)
    curve_full.to_csv( output_dir / "equity_curve_full.csv",  index=False)

    # Per-market P&L
    mkt_pnl.to_csv(output_dir / "per_market_pnl.csv", index=False)

    # Key metrics summary (add MC percentile rank)
    rows = []
    for key, val in metrics.items():
        rows.append({"metric": key, "value": round(val, 6) if isinstance(val, float) else val})
    if pct_rank_mc is not None:
        rows.append({"metric": "mc_pct_rank", "value": round(pct_rank_mc, 2)})
    pd.DataFrame(rows).to_csv(output_dir / "key_metrics.csv", index=False)

    # MC neutral benchmark simulation means
    if mean_return_sims is not None:
        pd.DataFrame({"mean_return_sim": mean_return_sims}).to_csv(
            output_dir / "mc_neutral_means.csv", index=False)

    # Abnormal returns series
    if ar_series is not None and r_protrump is not None and r_neutral_mean is not None:
        pd.DataFrame({"ar": ar_series,
                      "r_protrump": r_protrump,
                      "r_neutral_mean": r_neutral_mean}).to_csv(
            output_dir / "abnormal_returns.csv", index=False)

    print(f"\n  CSV exports saved to {output_dir}")


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    print("\n" + "═" * 70)
    print("  POLYMARKET TRUMP TRACKER — THESIS ANALYSIS")
    print("  Political Bias in Online Prediction Markets")
    print("  University of Copenhagen  |  2026")
    print("═" * 70)

    # ── Load ─────────────────────────────────────────────────────────────────
    dca, snaps, subs, mkts = load_data()
    daily_snaps, price_lookup = build_price_table(snaps)

    # ── Build equity curves ───────────────────────────────────────────────────
    print("\n  Building equity curves …")
    curve_full  = build_equity_curve(dca, price_lookup)

    PROSP_DT  = pd.to_datetime(PROSPECTIVE_START)
    CLEAN_DT  = pd.to_datetime(CLEAN_START)

    curve_retro = curve_full[curve_full["date"] <  PROSP_DT].copy().reset_index(drop=True)
    curve_prosp = curve_full[curve_full["date"] >= PROSP_DT].copy().reset_index(drop=True)
    curve_clean = curve_full[curve_full["date"] >= CLEAN_DT ].copy().reset_index(drop=True)

    print(f"  Full series         : {curve_full['date'].min().date()} → {curve_full['date'].max().date()}  ({len(curve_full)} days)")
    print(f"  Retrospective period: {curve_retro['date'].min().date()} → {curve_retro['date'].max().date()}  ({len(curve_retro)} days)")
    print(f"  Prospective — full  : {curve_prosp['date'].min().date()} → {curve_prosp['date'].max().date()}  ({len(curve_prosp)} days)")
    print(f"  Prospective — clean : {curve_clean['date'].min().date()} → {curve_clean['date'].max().date()}  ({len(curve_clean)} days)")

    # ── Neutral benchmark Monte Carlo ─────────────────────────────────────────
    print("\n  Building neutral benchmark Monte Carlo (10,000 sims) …")
    _, mc_date_range, yes_pnl_mat, no_pnl_mat, yes_cost_mat, no_cost_mat = \
        build_per_market_pnl_curves(dca, price_lookup)
    dr_sims, mean_sims, pnl_sims_mc = build_neutral_mc(
        yes_pnl_mat, no_pnl_mat, yes_cost_mat, no_cost_mat)
    ar_series, r_protrump, r_neutral_mean = compute_abnormal_returns(curve_clean, dr_sims)
    pct_rank_mc = float((mean_sims < r_protrump.mean()).mean() * 100)
    print(f"  MC complete: {len(mean_sims):,} sims  |  "
          f"pro-Trump at {pct_rank_mc:.1f}th percentile of neutral benchmark")

    # ── Per-market P&L ────────────────────────────────────────────────────────
    mkt_pnl = compute_per_market_pnl(dca, price_lookup, daily_snaps)

    # ── Risk metrics (clean series as primary) ────────────────────────────────
    metrics = compute_risk_metrics(curve_clean, label="CLEAN SERIES")

    # ── Print all analysis sections ───────────────────────────────────────────
    print_portfolio_overview(curve_clean, mkt_pnl)
    print_diagnostics_summary(curve_clean)
    print_hypothesis_tests(curve_clean, curve_full,
                           ar_series, r_protrump, dr_sims, mean_sims, pct_rank_mc)
    print_risk_metrics(metrics)
    print_per_market(mkt_pnl)

    # ── Section 9 — Retrospective vs Prospective ─────────────────────────────
    print_retro_prosp_comparison(curve_retro, curve_prosp, curve_clean)

    # ── Figures ───────────────────────────────────────────────────────────────
    section("SECTION 7 — GENERATING FIGURES")
    print()

    fig1_equity_curve(curve_full, prosp_start=PROSPECTIVE_START)
    fig2_daily_pnl(curve_clean)
    fig3_return_distribution(curve_clean)
    fig4_qq_plot(curve_clean)
    fig5_acf_pacf(curve_clean)
    fig6_drawdown(curve_clean)
    fig7_market_pnl(mkt_pnl)
    fig8_mc_equity_comparison(curve_full, pnl_sims_mc, mc_date_range, prosp_start=PROSPECTIVE_START)
    fig9_rolling_sharpe(curve_clean)
    if len(curve_retro) > 5:
        fig10_retro_vs_prosp(curve_retro, curve_prosp)
    fig11_mc_benchmark(mean_sims, dr_sims, r_protrump, mc_date_range, pct_rank_mc)

    # ── Export ────────────────────────────────────────────────────────────────
    section("SECTION 8 — EXPORTING DATA")
    print()
    export_results(curve_clean, curve_full, mkt_pnl, metrics, OUTPUT_DIR,
                   mean_return_sims=mean_sims, ar_series=ar_series,
                   r_protrump=r_protrump, r_neutral_mean=r_neutral_mean,
                   pct_rank_mc=pct_rank_mc)

    print("\n" + "═" * 70)
    print("  ANALYSIS COMPLETE")
    print(f"  Figures : {FIGURES_DIR}")
    print(f"  Data    : {OUTPUT_DIR}")
    print("═" * 70 + "\n")


if __name__ == "__main__":
    main()
