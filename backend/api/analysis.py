"""Analysis results API — serves pre-computed figures and metrics."""

import datetime
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()

OUTPUT_DIR  = Path("/app/analysis/output")
FIGURES_DIR = OUTPUT_DIR / "figures"
PROSP_START = "2026-01-26"

FIGURE_META = [
    ("fig1_equity_curve.png",        "Portfolio Value vs Invested Capital",    "Full timeline with retrospective / prospective divider"),
    ("fig2_daily_pnl.png",           "Daily P&L Changes",                      "Green = portfolio gained value; red = lost"),
    ("fig3_return_distribution.png", "Distribution of Daily Returns",          "Histogram with KDE and normal overlay"),
    ("fig4_qq_plot.png",             "Q-Q Plot",                               "Normality check — points on the line = normal"),
    ("fig5_acf_pacf.png",            "ACF / PACF",                             "Serial correlation test on daily returns"),
    ("fig6_drawdown.png",            "Portfolio Drawdown",                     "Peak-to-trough decline in portfolio value (%)"),
    ("fig7_market_pnl.png",          "Per-Market Unrealised P&L",              "Top 20 winning and losing markets"),
    ("fig8_pro_vs_anti.png",         "Pro-Trump vs Anti-Trump Counterfactual", "Directional bias comparison"),
    ("fig9_rolling_sharpe.png",      "Rolling 20-Day Sharpe Ratio",            "Risk-adjusted performance over time"),
    ("fig10_retro_vs_prosp.png",     "Retrospective vs Prospective",           "Period comparison (professor's suggested split)"),
]


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

    return result
