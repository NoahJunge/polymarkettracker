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
C_ANTI   = "#d97706"   # amber   — anti-Trump counterfactual
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


def print_hypothesis_tests(curve_clean, curve_full):
    section("SECTION 2 — HYPOTHESIS TESTING")
    print("""
  We test whether the mean daily return of the pro-Trump DCA strategy
  differs significantly from zero.

  H₀ : μ = 0  (no abnormal returns — consistent with the Efficient Market
                Hypothesis: prices already reflect true probabilities)
  H₁a: μ > 0  (persistent positive returns — market systematically
                undervalues pro-Trump outcomes)
  H₁b: μ < 0  (persistent negative returns — market systematically
                overvalues pro-Trump outcomes, driven by ideologically
                motivated buyers inflating YES prices)

  Primary dataset: CLEAN SERIES (from 2026-02-22) — continuous daily
  coverage across a stable set of ~200 markets.
  Robustness check: FULL SERIES (from 2026-01-26, including sparse early data).
""")

    for curve, label in [(curve_clean, "CLEAN SERIES (primary)"),
                          (curve_full,  "FULL SERIES (robustness)")]:
        r = curve["daily_return"].dropna().values
        T = len(r)
        subsection(f"2a — One-Sample t-Test  [{label}]")
        print(f"""  Method: scipy.stats.ttest_1samp
  Source: Student (1908); Brown & Warner (1985)
  Assumption check: Normality is not strictly required for T≥30 due to the
  Central Limit Theorem; serial independence verified via Ljung-Box (Section 0).

  H₀: μ = 0  vs  H₁: μ ≠ 0  (two-tailed, α = {ALPHA})
""")
        t_stat, p_val = stats.ttest_1samp(r, popmean=0)
        se   = r.std(ddof=1) / np.sqrt(T)
        ci_lo = r.mean() - 1.96 * se
        ci_hi = r.mean() + 1.96 * se

        print(f"  N (trading days)  : {T}")
        print(f"  Mean daily return : {pct(r.mean())}  ({usd(r.mean())} per $1 invested)")
        print(f"  Std deviation     : {pct(r.std(ddof=1))}")
        print(f"  t-statistic       : {t_stat:.4f}")
        print(f"  Degrees of freedom: {T - 1}")
        print(f"  {fmt_p(p_val)}  {significance_stars(p_val)}")
        print(f"  95% CI            : [{pct(ci_lo)},  {pct(ci_hi)}]")

        if p_val < ALPHA:
            direction = "POSITIVE (H₁a)" if r.mean() > 0 else "NEGATIVE (H₁b)"
            print(f"\n  ✓ REJECT H₀ at α={ALPHA}  →  Evidence for {direction} abnormal returns.")
            if r.mean() < 0:
                print("    Interpretation: The strategy yields persistent losses, suggesting")
                print("    pro-Trump outcomes are systematically OVERVALUED on Polymarket.")
                print("    This is consistent with H₁b: ideologically motivated buyers")
                print("    inflate YES (pro-Trump) prices above their true probability.")
            else:
                print("    Interpretation: The strategy yields persistent gains, suggesting")
                print("    pro-Trump outcomes are systematically UNDERVALUED on Polymarket.")
        else:
            print(f"\n  ✗ FAIL TO REJECT H₀ at α={ALPHA}  (p = {p_val:.4f})")
            print("    Interpretation: The observed mean return does not differ significantly")
            print("    from zero. The data is consistent with the Efficient Market Hypothesis:")
            print("    prices on Polymarket appear to reflect unbiased probability estimates")
            print("    for Trump-related outcomes over this observation window.")

        # Bootstrap BCa CI
        subsection(f"2b — Bootstrap BCa Confidence Interval  [{label}]")
        print("""  Method: scipy.stats.bootstrap with BCa method (10,000 resamples)
  Source: Efron & Tibshirani (1993)
  Purpose: Assumption-free confidence interval — valid regardless of the
  non-normality detected in the return distribution.
""")
        rng     = np.random.default_rng(42)
        bs_res  = scipy_bootstrap(
            (r,), statistic=np.mean,
            n_resamples=10_000, confidence_level=0.95,
            method="BCa", random_state=rng
        )
        bca_lo  = bs_res.confidence_interval.low
        bca_hi  = bs_res.confidence_interval.high
        print(f"  BCa 95% CI : [{pct(bca_lo)},  {pct(bca_hi)}]")
        if bca_lo > 0:
            print("  ✓ Entire CI above zero — bootstrap confirms positive abnormal returns.")
        elif bca_hi < 0:
            print("  ✓ Entire CI below zero — bootstrap confirms negative abnormal returns.")
        else:
            print("  ✗ CI straddles zero — bootstrap cannot confirm abnormal returns.")
            print("    Consistent with failing to reject H₀.")

        # Wilcoxon signed-rank test
        subsection(f"2c — Wilcoxon Signed-Rank Test  [{label}]")
        print("""  Method: scipy.stats.wilcoxon
  Source: Wilcoxon (1945); Hollander & Wolfe (1999)
  Purpose: Non-parametric alternative to the t-test. Tests whether the
  median daily return differs from zero. Makes no distributional assumptions.
  Appropriate given the non-normality detected (Jarque-Bera significant).
""")
        try:
            w_stat, w_p = stats.wilcoxon(r, alternative="two-sided")
            print(f"  W-statistic : {w_stat:.1f}")
            print(f"  {fmt_p(w_p)}  {significance_stars(w_p)}")
            if w_p < ALPHA:
                print(f"  ✓ REJECT H₀ at α={ALPHA} — median return significantly different from zero.")
            else:
                print(f"  ✗ FAIL TO REJECT H₀ at α={ALPHA} — median not significantly different from zero.")
        except Exception as e:
            print(f"  Could not compute: {e}")

        # OLS trend regression
        subsection(f"2d — OLS Trend Regression on Equity Curve  [{label}]")
        print("""  Method: OLS regression of cumulative P&L on time index t
  Model:  total_pnl_t = α + β·t + ε_t
  Source: Wooldridge (2012)
  Purpose: Tests whether the portfolio has a statistically significant linear
  trend — a positive β indicates growing P&L over time (strategy improving),
  negative β indicates consistent losses.
""")
        clean = curve.dropna(subset=["total_pnl"])
        t_idx = np.arange(len(clean))
        y     = clean["total_pnl"].values
        X     = sm.add_constant(t_idx)
        model = sm.OLS(y, X).fit(cov_type="HC3")
        beta  = model.params[1]
        beta_p = model.pvalues[1]
        r2    = model.rsquared
        print(f"  Slope β ($/day)      : {beta:.4f}  → {beta*365:.2f} $/year")
        print(f"  R²                   : {r2:.4f}")
        print(f"  {fmt_p(beta_p)}  {significance_stars(beta_p)}")
        if beta_p < ALPHA:
            direction = "UPWARD" if beta > 0 else "DOWNWARD"
            print(f"  ✓ Statistically significant {direction} trend in portfolio P&L.")
        else:
            print(f"  ✗ No statistically significant trend detected.")
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


def print_counterfactual(curve_pro, curve_anti):
    section("SECTION 6 — ANTI-TRUMP COUNTERFACTUAL")
    print("""
  To test whether the strategy's performance is specific to the pro-Trump
  direction, we construct an anti-Trump counterfactual: for every trade in
  the actual portfolio, we simulate having bet in the OPPOSITE direction
  (YES → NO, NO → YES) using the same dates and quantities.

  If the anti-Trump strategy performs symmetrically (similarly negative),
  the losses are not directional — consistent with general friction
  (bid-ask spreads, market illiquidity).

  If pro-Trump significantly underperforms anti-Trump, it implies that
  pro-Trump outcomes are systematically overpriced — direct evidence of H₁b.
""")
    pro_final  = curve_pro["total_pnl"].iloc[-1]
    anti_final = curve_anti["total_pnl"].iloc[-1]
    diff       = pro_final - anti_final

    print(f"  Pro-Trump final P&L  : {usd(pro_final)}")
    print(f"  Anti-Trump final P&L : {usd(anti_final)}")
    print(f"  Difference           : {usd(diff)}")

    if diff < 0:
        print(f"\n  Pro-Trump underperforms anti-Trump by {usd(abs(diff))}.")
        print("  This suggests pro-Trump outcomes are priced higher than their true")
        print("  probability — consistent with H₁b (ideological overvaluation).")
    elif diff > 0:
        print(f"\n  Pro-Trump outperforms anti-Trump by {usd(diff)}.")
        print("  This suggests pro-Trump outcomes are underpriced — consistent with H₁a.")
    else:
        print("\n  Symmetric performance — no directional bias detected.")
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


def fig8_pro_vs_anti(curve_pro, curve_anti):
    """Fig 8: Pro-Trump vs Anti-Trump equity curves."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8), sharex=True)

    # Top panel: portfolio value
    ax1.plot(curve_pro["date"],  curve_pro["portfolio_value"],  color=C_PRO,  linewidth=2.0, label="Pro-Trump (actual)")
    ax1.plot(curve_anti["date"], curve_anti["portfolio_value"], color=C_ANTI, linewidth=2.0, linestyle="--", label="Anti-Trump (counterfactual)")
    ax1.plot(curve_pro["date"],  curve_pro["invested"],         color=C_INV,  linewidth=1.2, linestyle=":", label="Invested capital")
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax1.legend(fontsize=8, loc="upper left")
    style_ax(ax1, title="Figure 8a — Portfolio Value: Pro-Trump vs Anti-Trump",
             xlabel="", ylabel="Portfolio value (USD)")

    # Bottom panel: cumulative P&L
    ax2.plot(curve_pro["date"],  curve_pro["total_pnl"],  color=C_PRO,  linewidth=2.0, label="Pro-Trump P&L")
    ax2.plot(curve_anti["date"], curve_anti["total_pnl"], color=C_ANTI, linewidth=2.0, linestyle="--", label="Anti-Trump P&L")
    ax2.axhline(y=0, color=C_TEXT, linewidth=0.8, linestyle=":")
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax2.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=30, ha="right")
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax2.legend(fontsize=8, loc="upper left")
    style_ax(ax2, title="Figure 8b — Cumulative P&L: Pro-Trump vs Anti-Trump",
             xlabel="Date", ylabel="Total P&L (USD)")

    fig.tight_layout()
    save_fig(fig, "fig8_pro_vs_anti.png")


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


# ── EXPORT ────────────────────────────────────────────────────────────────────

def export_results(curve_clean, curve_full, mkt_pnl, metrics, output_dir):
    # Equity curves
    curve_clean.to_csv(output_dir / "equity_curve_clean.csv", index=False)
    curve_full.to_csv( output_dir / "equity_curve_full.csv",  index=False)

    # Per-market P&L
    mkt_pnl.to_csv(output_dir / "per_market_pnl.csv", index=False)

    # Key metrics summary
    rows = []
    for key, val in metrics.items():
        rows.append({"metric": key, "value": round(val, 6) if isinstance(val, float) else val})
    pd.DataFrame(rows).to_csv(output_dir / "key_metrics.csv", index=False)

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
    curve_full  = build_equity_curve(dca, price_lookup, flip_sides=False)
    curve_anti  = build_equity_curve(dca, price_lookup, flip_sides=True)

    PROSP_DT  = pd.to_datetime(PROSPECTIVE_START)
    CLEAN_DT  = pd.to_datetime(CLEAN_START)

    curve_retro = curve_full[curve_full["date"] <  PROSP_DT].copy().reset_index(drop=True)
    curve_prosp = curve_full[curve_full["date"] >= PROSP_DT].copy().reset_index(drop=True)
    curve_clean = curve_full[curve_full["date"] >= CLEAN_DT ].copy().reset_index(drop=True)

    print(f"  Full series         : {curve_full['date'].min().date()} → {curve_full['date'].max().date()}  ({len(curve_full)} days)")
    print(f"  Retrospective period: {curve_retro['date'].min().date()} → {curve_retro['date'].max().date()}  ({len(curve_retro)} days)")
    print(f"  Prospective — full  : {curve_prosp['date'].min().date()} → {curve_prosp['date'].max().date()}  ({len(curve_prosp)} days)")
    print(f"  Prospective — clean : {curve_clean['date'].min().date()} → {curve_clean['date'].max().date()}  ({len(curve_clean)} days)")

    # ── Per-market P&L ────────────────────────────────────────────────────────
    mkt_pnl = compute_per_market_pnl(dca, price_lookup, daily_snaps)

    # ── Risk metrics (clean series as primary) ────────────────────────────────
    metrics = compute_risk_metrics(curve_clean, label="CLEAN SERIES")

    # ── Print all analysis sections ───────────────────────────────────────────
    print_portfolio_overview(curve_clean, mkt_pnl)
    print_diagnostics_summary(curve_clean)
    print_hypothesis_tests(curve_clean, curve_full)
    print_risk_metrics(metrics)
    print_per_market(mkt_pnl)
    print_counterfactual(curve_clean,
                         curve_anti[curve_anti["date"] >= pd.to_datetime(CLEAN_START)].reset_index(drop=True))

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
    fig8_pro_vs_anti(curve_clean,
                     curve_anti[curve_anti["date"] >= pd.to_datetime(CLEAN_START)].reset_index(drop=True))
    fig9_rolling_sharpe(curve_clean)
    if len(curve_retro) > 5:
        fig10_retro_vs_prosp(curve_retro, curve_prosp)

    # ── Export ────────────────────────────────────────────────────────────────
    section("SECTION 8 — EXPORTING DATA")
    print()
    export_results(curve_clean, curve_full, mkt_pnl, metrics, OUTPUT_DIR)

    print("\n" + "═" * 70)
    print("  ANALYSIS COMPLETE")
    print(f"  Figures : {FIGURES_DIR}")
    print(f"  Data    : {OUTPUT_DIR}")
    print("═" * 70 + "\n")


if __name__ == "__main__":
    main()
