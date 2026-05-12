"""
Diagnostic script — runs before any formal analysis.
Reconstructs daily portfolio returns from seed.xlsx, then tests:
  1. Descriptive statistics
  2. Normality (Shapiro-Wilk, Jarque-Bera)
  3. Serial independence (Ljung-Box at lags 1,5,10, Durbin-Watson)
  4. Stationarity (ADF)
  5. Summary recommendation on which formal tests are valid

YES bets are valued at yes_price; NO bets (pro-Trump on NO side) at no_price.
"""

import json
import sys
import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.stattools import adfuller
from statsmodels.stats.stattools import durbin_watson

SEED = "/Users/Noah/Desktop/polymarkettracker/backend/seed_data/seed.xlsx"
CLEAN_START = "2026-02-22"   # reliable daily coverage begins here


# ── helpers ──────────────────────────────────────────────────────────────────

def norm_id(x):
    try:
        return str(int(float(x)))
    except Exception:
        return str(x)


def load_data(path):
    print(f"Loading {path} …")
    trades = pd.read_excel(path, sheet_name="paper_trades")
    snaps  = pd.read_excel(path, sheet_name="snapshots_wide")
    subs   = pd.read_excel(path, sheet_name="dca_subscriptions")
    print(f"  trades: {len(trades):,}  |  snapshots: {len(snaps):,}  |  subscriptions: {len(subs):,}")
    return trades, snaps, subs


# ── equity curve ─────────────────────────────────────────────────────────────

def build_equity_curve(trades_raw, snaps_raw):
    """
    Returns a daily DataFrame with columns:
        date, portfolio_value, invested, total_pnl, daily_pnl_change, daily_return
    """
    # --- parse trades ---
    trades = trades_raw.copy()
    trades["meta"] = trades["metadata"].apply(
        lambda x: json.loads(x) if isinstance(x, str) else (x if isinstance(x, dict) else {})
    )
    dca = trades[trades["meta"].apply(lambda x: x.get("dca") == True)].copy()
    dca["market_id"] = dca["market_id"].apply(norm_id)
    dca["side"]      = dca["side"].str.upper()
    dca["date"]      = pd.to_datetime(dca["created_at_utc"], format="mixed", utc=True).dt.date
    dca["price"]     = pd.to_numeric(dca["price"], errors="coerce")
    dca["quantity"]  = pd.to_numeric(dca["quantity"], errors="coerce")
    dca = dca.sort_values("date")

    opens  = dca[dca["action"].str.upper() == "OPEN"].copy()
    closes = dca[dca["action"].str.upper() == "CLOSE"].copy()
    print(f"\nDCA OPEN trades:  {len(opens):,}")
    print(f"DCA CLOSE trades: {len(closes):,}")

    # --- parse snapshots ---
    snaps = snaps_raw.copy()
    snaps["market_id"]  = snaps["market_id"].apply(norm_id)
    snaps["date"]       = pd.to_datetime(snaps["timestamp_utc"], format="mixed", utc=True).dt.date
    snaps["yes_price"]  = pd.to_numeric(snaps["yes_price"], errors="coerce")
    snaps["no_price"]   = pd.to_numeric(snaps["no_price"], errors="coerce")

    # last snapshot per (market, date)
    daily = (
        snaps.sort_values("timestamp_utc")
             .groupby(["market_id", "date"])
             .last()
             .reset_index()[["market_id", "date", "yes_price", "no_price"]]
    )

    # --- date range ---
    all_dates = sorted(set(opens["date"]) | set(daily["date"]))
    date_range = pd.date_range(min(all_dates), max(all_dates), freq="D").date

    # --- FIFO lots: (market_id, side) -> list of (qty, entry_price) ---
    lots = {}
    realized_pnl = 0.0
    price_lookup = {}   # (market_id, date) -> {yes_price, no_price}

    for row in daily.itertuples(index=False):
        price_lookup[(row.market_id, row.date)] = {
            "yes_price": row.yes_price,
            "no_price":  row.no_price,
        }

    # index opens/closes by date for fast lookup
    opens_by_date  = opens.groupby("date")
    closes_by_date = closes.groupby("date") if len(closes) > 0 else {}

    curve = []
    last_prices = {}   # market_id -> {yes_price, no_price}  (carry forward)

    for d in date_range:
        # update last known prices
        for mid in daily[daily["date"] == d]["market_id"]:
            key = (mid, d)
            if key in price_lookup:
                last_prices[mid] = price_lookup[key]

        # process closes first (FIFO)
        if isinstance(closes_by_date, pd.core.groupby.DataFrameGroupBy) and d in closes_by_date.groups:
            for row in closes_by_date.get_group(d).itertuples(index=False):
                key = (row.market_id, row.side)
                close_qty = row.quantity
                close_price = row.price
                if key in lots:
                    remaining = close_qty
                    while remaining > 1e-9 and lots[key]:
                        q, ep = lots[key][0]
                        matched = min(q, remaining)
                        realized_pnl += matched * (close_price - ep)
                        lots[key][0] = (q - matched, ep)
                        if lots[key][0][0] < 1e-9:
                            lots[key].pop(0)
                        remaining -= matched

        # process new opens
        if d in opens_by_date.groups:
            for row in opens_by_date.get_group(d).itertuples(index=False):
                key = (row.market_id, row.side)
                if key not in lots:
                    lots[key] = []
                lots[key].append((row.quantity, row.price))

        # mark to market
        portfolio_value = 0.0
        invested = 0.0
        for (mid, side), position_lots in lots.items():
            total_qty = sum(q for q, _ in position_lots)
            if total_qty < 1e-9:
                continue
            cost = sum(q * p for q, p in position_lots)
            prices = last_prices.get(mid)
            if prices:
                cp = prices["yes_price"] if side == "YES" else prices["no_price"]
            else:
                cp = sum(q * p for q, p in position_lots) / total_qty  # fallback: entry price
            portfolio_value += total_qty * cp
            invested += cost

        total_pnl = portfolio_value - invested + realized_pnl
        curve.append({"date": d, "portfolio_value": portfolio_value,
                      "invested": invested, "total_pnl": total_pnl})

    df = pd.DataFrame(curve)
    df["daily_pnl_change"] = df["total_pnl"].diff()

    # time-weighted daily return: pnl change / prior invested (avoid div-by-zero)
    prior_inv = df["invested"].shift(1)
    df["daily_return"] = np.where(prior_inv > 1e-6,
                                  df["daily_pnl_change"] / prior_inv,
                                  np.nan)
    return df


# ── diagnostics ──────────────────────────────────────────────────────────────

def run_diagnostics(curve, label):
    r = curve["daily_return"].dropna()
    pnl = curve["daily_pnl_change"].dropna()

    print(f"\n{'='*60}")
    print(f"  DIAGNOSTICS — {label}  (T = {len(r)} daily obs.)")
    print(f"{'='*60}")

    # --- 1. Descriptive stats ---
    print("\n[1] DESCRIPTIVE STATISTICS (daily returns)")
    print(f"    Mean:       {r.mean():.6f}  ({r.mean()*100:.4f}%)")
    print(f"    Std dev:    {r.std(ddof=1):.6f}")
    print(f"    Min:        {r.min():.6f}")
    print(f"    Max:        {r.max():.6f}")
    print(f"    Skewness:   {stats.skew(r):.4f}  (0 = symmetric)")
    print(f"    Kurtosis:   {stats.kurtosis(r):.4f}  (0 = normal, >0 = fat tails)")
    print(f"    Mean daily P&L change: ${pnl.mean():.4f}")

    # --- 2. Normality tests ---
    print("\n[2] NORMALITY TESTS")
    if len(r) >= 3:
        sw_stat, sw_p = stats.shapiro(r)
        print(f"    Shapiro-Wilk:  W={sw_stat:.4f},  p={sw_p:.4f}  "
              f"→ {'REJECT normality' if sw_p < 0.05 else 'cannot reject normality'} at α=0.05")
    jb_result = stats.jarque_bera(r)
    jb_stat, jb_p = jb_result.statistic, jb_result.pvalue
    print(f"    Jarque-Bera:   JB={jb_stat:.4f}, p={jb_p:.4f}  "
          f"→ {'REJECT normality' if jb_p < 0.05 else 'cannot reject normality'} at α=0.05")

    # --- 3. Serial independence (Ljung-Box) ---
    print("\n[3] SERIAL INDEPENDENCE — Ljung-Box Q-test")
    max_lag = min(10, len(r) // 5)
    if max_lag < 1:
        print("    Insufficient observations for Ljung-Box.")
    else:
        lags_to_test = [l for l in [1, 5, 10] if l <= max_lag]
        lb = acorr_ljungbox(r, lags=lags_to_test, return_df=True)
        for lag in lags_to_test:
            row = lb.loc[lag]
            print(f"    Lag {lag:2d}:  Q={row['lb_stat']:.4f},  p={row['lb_pvalue']:.4f}  "
                  f"→ {'AUTOCORRELATION detected' if row['lb_pvalue'] < 0.05 else 'no autocorrelation'}")

    # --- 4. Durbin-Watson ---
    print("\n[4] DURBIN-WATSON (lag-1 autocorrelation)")
    dw = durbin_watson(r)
    print(f"    DW = {dw:.4f}  (2.0 = no autocorrelation, <2 = positive, >2 = negative)")

    # --- 5. Stationarity (ADF) ---
    print("\n[5] STATIONARITY — Augmented Dickey-Fuller")
    if len(r) >= 10:
        adf_stat, adf_p, adf_lags, adf_nobs, adf_cv, _ = adfuller(r, autolag="AIC")
        print(f"    ADF stat: {adf_stat:.4f},  p={adf_p:.4f},  lags used: {adf_lags}")
        print(f"    Critical values: 1%={adf_cv['1%']:.3f}, 5%={adf_cv['5%']:.3f}, 10%={adf_cv['10%']:.3f}")
        print(f"    → {'STATIONARY (reject unit root)' if adf_p < 0.05 else 'non-stationary or inconclusive'}")
    else:
        print("    Insufficient observations for ADF.")

    # --- 6. Recommendation ---
    sw_reject   = sw_p < 0.05 if len(r) >= 3 else False
    jb_reject   = jb_p < 0.05
    lb1_reject  = lb.loc[1]["lb_pvalue"] < 0.05 if 1 in lags_to_test else False

    print(f"\n[6] RECOMMENDATION")
    if lb1_reject:
        print("    ⚠  Autocorrelation detected (Ljung-Box lag-1 significant).")
        print("       → Use Newey-West HAC-robust t-test as PRIMARY result.")
        print("       → Standard t-test still reported but flagged as secondary.")
    else:
        print("    ✓  No significant autocorrelation at lag-1.")
        print("       → Standard t-test on mean return is valid.")

    if sw_reject or jb_reject:
        print("    ⚠  Non-normality detected.")
        print("       → Bootstrap BCa confidence interval recommended alongside t-test.")
        print("       → Mann-Whitney U or Wilcoxon signed-rank as non-parametric alternative.")
    else:
        print("    ✓  Normality cannot be rejected — t-test assumptions largely satisfied.")

    print()
    return {"T": len(r), "mean_return": r.mean(), "std_return": r.std(ddof=1),
            "skewness": stats.skew(r), "kurtosis": stats.kurtosis(r),
            "sw_p": sw_p if len(r) >= 3 else None,
            "jb_p": jb_p, "lb1_p": lb.loc[1]["lb_pvalue"] if 1 in lags_to_test else None,
            "dw": dw}


# ── main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    trades_raw, snaps_raw, subs_raw = load_data(SEED)

    print("\nBuilding equity curve from all data …")
    curve_full = build_equity_curve(trades_raw, snaps_raw)
    print(f"  Date range: {curve_full['date'].min()} → {curve_full['date'].max()}")
    print(f"  Total days: {len(curve_full)}")

    # Full series (Jan 26 onward)
    run_diagnostics(curve_full, "FULL SERIES (Jan 26 – present)")

    # Clean series (Feb 22 onward — reliable daily coverage)
    curve_clean = curve_full[curve_full["date"] >= pd.to_datetime(CLEAN_START).date()].copy()
    run_diagnostics(curve_clean, f"CLEAN SERIES ({CLEAN_START} – present)")
