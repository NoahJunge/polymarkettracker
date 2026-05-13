"""Analysis results API — serves pre-computed figures and metrics."""

import datetime
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Make run_analysis importable
_ANALYSIS_DIR = str(Path(__file__).parent.parent / "analysis")
if _ANALYSIS_DIR not in sys.path:
    sys.path.insert(0, _ANALYSIS_DIR)


class MCRequest(BaseModel):
    n_sims: int = 1000
    seed: int = 42

router = APIRouter()

OUTPUT_DIR  = Path("/app/analysis/output")
FIGURES_DIR = OUTPUT_DIR / "figures"
PROSP_START = "2026-01-26"

FIGURE_META = [
    ("fig1_equity_curve.png",        "Portfolio Value vs Invested Capital",  "Full timeline with retrospective / prospective divider"),
    ("fig2_daily_pnl.png",           "Daily P&L Changes",                    "Green = portfolio gained value; red = lost"),
    ("fig3_return_distribution.png", "Distribution of Daily Returns",        "Histogram with KDE and normal overlay"),
    ("fig4_qq_plot.png",             "Q-Q Plot",                             "Normality check — points on the line = normal"),
    ("fig5_acf_pacf.png",            "ACF / PACF",                           "Serial correlation test on daily returns"),
    ("fig6_drawdown.png",            "Portfolio Drawdown",                   "Peak-to-trough decline in portfolio value (%)"),
    ("fig7_market_pnl.png",             "Per-Market Unrealised P&L",                     "Top 20 winning and losing markets"),
    ("fig8_mc_equity_comparison.png",  "Pro-Trump vs Neutral Benchmark — Equity Curve", "Cumulative P&L: actual vs 10,000 random-direction simulations"),
    ("fig9_rolling_sharpe.png",        "Rolling 20-Day Sharpe Ratio",                   "Risk-adjusted performance over time"),
    ("fig10_retro_vs_prosp.png",     "Retrospective vs Prospective",         "Period comparison (professor's suggested split)"),
    ("fig11_mc_benchmark.png",       "Neutral Benchmark Monte Carlo",        "10,000 random-direction simulations vs pro-Trump"),
    ("fig12_strategy_comparison.png", "Pro-Trump vs Anti-Trump vs Neutral",  "Both strategy equity curves overlaid with neutral Monte Carlo benchmark"),
]

SEED_PATH = Path(__file__).parent.parent / "seed_data" / "seed.xlsx"

# ── MC data cache (invalidated when seed.xlsx changes) ───────────────────────
_mc_cache: dict = {}


def _get_mc_data():
    """Load + cache per-market P&L matrices. Reloads only when seed.xlsx changes."""
    import run_analysis as ra  # noqa: PLC0415

    mtime = SEED_PATH.stat().st_mtime if SEED_PATH.exists() else None
    if _mc_cache.get("mtime") == mtime and "yes_pnl" in _mc_cache:
        return _mc_cache

    dca, snaps, _subs, _mkts = ra.load_data()
    _, price_lookup = ra.build_price_table(snaps)
    curve_full = ra.build_equity_curve(dca, price_lookup)
    markets, date_range, yes_pnl, no_pnl, yes_cost, no_cost = \
        ra.build_per_market_pnl_curves(dca, price_lookup)

    _mc_cache.update(
        mtime=mtime,
        curve_full=curve_full,
        markets=markets,
        date_range=date_range,
        yes_pnl=yes_pnl,
        no_pnl=no_pnl,
        yes_cost=yes_cost,
        no_cost=no_cost,
    )
    return _mc_cache


@router.get("/analysis/figures/{filename}")
async def get_figure(filename: str):
    if not filename.endswith(".png"):
        raise HTTPException(400, "Only PNG files supported")
    path = FIGURES_DIR / filename
    if not path.exists():
        raise HTTPException(404, "Figure not found — run analysis first")
    return FileResponse(str(path), media_type="image/png")


@router.get("/analysis/status")
async def get_analysis_status():
    metrics_path = OUTPUT_DIR / "key_metrics.csv"
    last_run = None
    if metrics_path.exists():
        ts = metrics_path.stat().st_mtime
        last_run = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).isoformat()

    figures = [
        {
            "filename": f,
            "title": title,
            "caption": caption,
            "exists": (FIGURES_DIR / f).exists(),
        }
        for f, title, caption in FIGURE_META
    ]
    available = sum(1 for fig in figures if fig["exists"])
    return {
        "figures_available": available,
        "figures_total": len(FIGURE_META),
        "metrics_available": metrics_path.exists(),
        "last_run_utc": last_run,
        "figures": figures,
    }


@router.get("/analysis/metrics")
async def get_metrics():
    metrics_path = OUTPUT_DIR / "key_metrics.csv"
    equity_full  = OUTPUT_DIR / "equity_curve_full.csv"
    mkt_pnl_path = OUTPUT_DIR / "per_market_pnl.csv"

    if not metrics_path.exists():
        raise HTTPException(404, "Metrics not found — run analysis first")

    metrics_df = pd.read_csv(metrics_path)
    metrics = {}
    for _, row in metrics_df.iterrows():
        val = row["value"]
        try:
            val = float(val)
        except (ValueError, TypeError):
            pass
        metrics[row["metric"]] = val

    result = {"metrics": metrics}

    # MC neutral benchmark summary
    mc_path = OUTPUT_DIR / "mc_neutral_means.csv"
    ar_path = OUTPUT_DIR / "abnormal_returns.csv"
    if mc_path.exists():
        mc_df = pd.read_csv(mc_path)
        sims  = mc_df["mean_return_sim"].values
        result["mc_benchmark"] = {
            "n_sims":    int(len(sims)),
            "mc_mean":   round(float(sims.mean()), 8),
            "mc_std":    round(float(sims.std()),  8),
            "mc_p5":     round(float(sims.quantile(0.05) if hasattr(sims, "quantile") else __import__("numpy").percentile(sims, 5)), 8),
            "mc_p95":    round(float(sims.quantile(0.95) if hasattr(sims, "quantile") else __import__("numpy").percentile(sims, 95)), 8),
            "pct_rank":  round(float(metrics.get("mc_pct_rank", 0)), 2),
        }
    if ar_path.exists():
        ar_df = pd.read_csv(ar_path)
        result["abnormal_returns_series"] = ar_df[["ar", "r_protrump", "r_neutral_mean"]].to_dict("records")

    if mkt_pnl_path.exists():
        mkt = pd.read_csv(mkt_pnl_path)
        gross_gain = mkt.loc[mkt["unrealised_pnl"] > 0, "unrealised_pnl"].sum()
        gross_loss = abs(mkt.loc[mkt["unrealised_pnl"] < 0, "unrealised_pnl"].sum())
        result["market_summary"] = {
            "total":        int(len(mkt)),
            "positive":     int((mkt["unrealised_pnl"] > 0).sum()),
            "negative":     int((mkt["unrealised_pnl"] < 0).sum()),
            "win_rate":     round(float((mkt["unrealised_pnl"] > 0).mean() * 100), 1),
            "total_pnl":    round(float(mkt["unrealised_pnl"].sum()), 4),
            "gross_gain":   round(float(gross_gain), 4),
            "gross_loss":   round(float(gross_loss), 4),
            "profit_factor": round(float(gross_gain / gross_loss), 4) if gross_loss > 0 else None,
        }

    if equity_full.exists():
        df = pd.read_csv(equity_full)
        df["date"] = pd.to_datetime(df["date"])
        retro = df[df["date"] <  PROSP_START].copy()
        prosp = df[df["date"] >= PROSP_START].copy()

        def _stats(sub, label):
            if sub.empty:
                return {"label": label, "days": 0}
            r    = sub["daily_return"].dropna()
            last = sub.iloc[-1]
            inv  = float(last["invested"])
            pnl  = float(last["total_pnl"])
            return {
                "label":        label,
                "days":         len(sub),
                "n_returns":    int(len(r)),
                "mean_return":  round(float(r.mean()), 6) if len(r) else None,
                "std_return":   round(float(r.std(ddof=1)), 6) if len(r) > 1 else None,
                "final_pnl":    round(pnl, 4),
                "invested":     round(inv, 4),
                "return_pct":   round(pnl / inv * 100, 2) if inv > 0 else 0,
                "date_start":   sub["date"].min().strftime("%Y-%m-%d"),
                "date_end":     sub["date"].max().strftime("%Y-%m-%d"),
            }

        result["periods"] = {
            "retrospective": _stats(retro, "Retrospective"),
            "prospective":   _stats(prosp, "Prospective"),
            "full":          _stats(df,    "Full Series"),
        }

        # Equity curve for sparkline (daily pnl, both periods)
        result["equity_series"] = df[["date", "total_pnl", "portfolio_value", "invested"]].assign(
            date=df["date"].dt.strftime("%Y-%m-%d")
        ).to_dict("records")

    # Anti-Trump metrics and equity series
    anti_metrics_path = OUTPUT_DIR / "key_metrics_anti.csv"
    anti_equity_path  = OUTPUT_DIR / "equity_curve_full_anti.csv"

    if anti_metrics_path.exists():
        anti_df = pd.read_csv(anti_metrics_path)
        anti_m: dict = {}
        for _, row in anti_df.iterrows():
            val = row["value"]
            try:
                val = float(val)
            except (ValueError, TypeError):
                pass
            anti_m[row["metric"]] = val
        result["anti_metrics"] = anti_m

    if anti_equity_path.exists():
        adf = pd.read_csv(anti_equity_path)
        adf["date"] = pd.to_datetime(adf["date"])
        retro_a = adf[adf["date"] <  PROSP_START].copy()
        prosp_a = adf[adf["date"] >= PROSP_START].copy()
        result["anti_equity_series"] = (
            adf[["date", "total_pnl", "portfolio_value", "invested"]]
            .assign(date=adf["date"].dt.strftime("%Y-%m-%d"))
            .to_dict("records")
        )
        result["anti_periods"] = {
            "retrospective": _stats(retro_a, "Retrospective"),
            "prospective":   _stats(prosp_a, "Prospective"),
            "full":          _stats(adf,     "Full Series"),
        }

    return result


@router.post("/analysis/monte-carlo")
async def run_monte_carlo_interactive(body: MCRequest):
    """Run an interactive neutral-benchmark Monte Carlo simulation.

    Loads seed.xlsx, builds per-market P&L matrices, runs n_sims 50/50
    random-direction simulations, and returns histogram + equity fan data.
    """
    if not SEED_PATH.exists():
        raise HTTPException(404, "seed.xlsx not found — ensure Docker volume is mounted")

    try:
        import run_analysis as ra  # noqa: PLC0415
    except ImportError as exc:
        raise HTTPException(500, f"Cannot import analysis module: {exc}") from exc

    n_sims = max(100, min(10_000, body.n_sims))

    try:
        cache = _get_mc_data()
        curve_full = cache["curve_full"]
        markets    = cache["markets"]
        date_range = cache["date_range"]
        yes_pnl    = cache["yes_pnl"]
        no_pnl     = cache["no_pnl"]
        yes_cost   = cache["yes_cost"]
        no_cost    = cache["no_cost"]

        if curve_full.empty:
            raise HTTPException(404, "No equity data — run the full analysis first")

        dr_sims, mean_return_sims, pnl_sims = ra.build_neutral_mc(
            yes_pnl, no_pnl, yes_cost, no_cost, n_sims=n_sims, seed=body.seed
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Monte Carlo computation failed: {exc}") from exc

    # ── stats ────────────────────────────────────────────────────────────────
    r_actual = curve_full["daily_return"].dropna().values
    pro_mean = float(np.nanmean(r_actual))
    mc_mean  = float(np.nanmean(mean_return_sims))
    mc_std   = float(np.nanstd(mean_return_sims))
    pct_rank = float((mean_return_sims < pro_mean).mean() * 100)
    emp_p_one = float((mean_return_sims >= pro_mean).mean())
    emp_p_two = float(min(2 * emp_p_one, 2 * (1 - emp_p_one)))

    verdict = (
        "underperforms" if pct_rank <= 5
        else "outperforms" if pct_rank >= 95
        else "neutral"
    )

    # ── histogram (60 bins) ──────────────────────────────────────────────────
    counts, edges = np.histogram(mean_return_sims, bins=60)
    histogram = [
        {
            "x":             round(float((lo + hi) / 2 * 100), 5),
            "count":         int(cnt),
            "below_protrump": bool(hi <= pro_mean),
        }
        for cnt, lo, hi in zip(counts, edges[:-1], edges[1:])
    ]

    # ── equity fan ───────────────────────────────────────────────────────────
    T = pnl_sims.shape[1]
    date_strs = [str(d) for d in date_range]

    curve_by_date = dict(zip(
        pd.to_datetime(curve_full["date"]).dt.strftime("%Y-%m-%d"),
        curve_full["total_pnl"].where(pd.notna(curve_full["total_pnl"])),
    ))

    p5_arr  = np.percentile(pnl_sims, 5,  axis=0)
    p25_arr = np.percentile(pnl_sims, 25, axis=0)
    p50_arr = np.percentile(pnl_sims, 50, axis=0)
    p75_arr = np.percentile(pnl_sims, 75, axis=0)
    p95_arr = np.percentile(pnl_sims, 95, axis=0)

    equity_fan = []
    for t in range(T):
        d_str = date_strs[t]
        pt_raw = curve_by_date.get(d_str)
        pt = None if pt_raw is None or (isinstance(pt_raw, float) and np.isnan(pt_raw)) else round(float(pt_raw), 4)
        equity_fan.append({
            "date":     d_str,
            "p5":       round(float(p5_arr[t]),  2),
            "p25":      round(float(p25_arr[t]), 2),
            "p50":      round(float(p50_arr[t]), 2),
            "p75":      round(float(p75_arr[t]), 2),
            "p95":      round(float(p95_arr[t]), 2),
            "protrump": pt,
        })

    return {
        "n_sims":          n_sims,
        "n_markets":       int(len(markets)),
        "pro_trump_mean":  round(pro_mean, 8),
        "mc_mean":         round(mc_mean,  8),
        "mc_std":          round(mc_std,   8),
        "mc_p5":           round(float(np.percentile(mean_return_sims, 5)),  8),
        "mc_p95":          round(float(np.percentile(mean_return_sims, 95)), 8),
        "pct_rank":        round(pct_rank,  2),
        "emp_p_one_tail":  round(emp_p_one, 6),
        "emp_p_two_tail":  round(emp_p_two, 6),
        "verdict":         verdict,
        "histogram":       histogram,
        "equity_fan":      equity_fan,
    }
