"""Generate a polished portfolio gain chart from the running backend API."""

import json
import urllib.request
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as mpatches
from matplotlib.ticker import FuncFormatter
from datetime import datetime
import numpy as np

# ── Fetch data ──────────────────────────────────────────────────────────────
url = "http://localhost:8000/api/paper_portfolio/equity_curve"
with urllib.request.urlopen(url) as r:
    data = json.load(r)

curve = data["curve"]
dates = [datetime.strptime(p["date"], "%Y-%m-%d") for p in curve]
pnl = [p["total_pnl"] for p in curve]
invested = [p["cumulative_invested"] for p in curve]
value = [p["portfolio_value"] for p in curve]

# ── Style ────────────────────────────────────────────────────────────────────
VIOLET   = "#7c3aed"
INDIGO   = "#4f46e5"
GREEN    = "#16a34a"
RED      = "#dc2626"
SLATE_50 = "#f8fafc"
SLATE_200= "#e2e8f0"
SLATE_500= "#64748b"
SLATE_700= "#334155"
SLATE_900= "#0f172a"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.spines.top": False,
    "axes.spines.right": False,
})

fig = plt.figure(figsize=(13, 7.5), facecolor="white")

# Title block
fig.text(0.055, 0.93, "Polymarket Trump Tracker — Portfolio Performance",
         fontsize=15, fontweight="bold", color=SLATE_900)
fig.text(0.055, 0.895,
         f"Paper trading · {dates[0].strftime('%b %d, %Y')} – {dates[-1].strftime('%b %d, %Y')}  ·  "
         f"{len(curve)} trading days  ·  {curve[-1]['total_open_trades']:,} trades placed",
         fontsize=9.5, color=SLATE_500)

# Divider line under title
fig.add_artist(plt.Line2D([0.055, 0.95], [0.875, 0.875],
               transform=fig.transFigure, color=SLATE_200, linewidth=1))

# ── Metric cards (top row) ───────────────────────────────────────────────────
final_pnl   = pnl[-1]
final_val   = value[-1]
final_inv   = invested[-1]
pnl_pct     = (final_pnl / final_inv * 100) if final_inv else 0
pnl_color   = GREEN if final_pnl >= 0 else RED
pnl_sign    = "+" if final_pnl >= 0 else ""
pct_sign    = "+" if pnl_pct >= 0 else ""

cards = [
    ("Total Invested",   f"${final_inv:,.2f}",  SLATE_700, None),
    ("Portfolio Value",  f"${final_val:,.2f}",  SLATE_700, None),
    ("Total P&L",        f"{pnl_sign}${abs(final_pnl):,.2f}", pnl_color, None),
    ("Return",           f"{pct_sign}{pnl_pct:.1f}%",  pnl_color, None),
]

card_x = [0.055, 0.30, 0.545, 0.75]
for i, (label, val_str, color, _) in enumerate(cards):
    x = card_x[i]
    fig.text(x, 0.845, label, fontsize=8.5, color=SLATE_500, fontweight="normal")
    fig.text(x, 0.805, val_str, fontsize=17, color=color, fontweight="bold")

# ── Main chart ───────────────────────────────────────────────────────────────
ax = fig.add_axes([0.055, 0.1, 0.895, 0.63])
ax.set_facecolor(SLATE_50)
ax.patch.set_alpha(0.4)

for spine in ax.spines.values():
    spine.set_edgecolor(SLATE_200)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.tick_params(colors=SLATE_500, labelsize=8.5)
ax.grid(axis="y", color=SLATE_200, linewidth=0.7, linestyle="--", alpha=0.8)

# Invested amount (dashed reference line)
ax.plot(dates, invested, color=SLATE_500, linewidth=1.5,
        linestyle="--", alpha=0.55, label="Cumulative Invested")

# Portfolio value (main line)
ax.plot(dates, value, color=VIOLET, linewidth=2.5,
        label="Portfolio Value", zorder=3)

# P&L shaded area (fill between invested and value)
ax.fill_between(dates, invested, value,
                where=[v >= inv for v, inv in zip(value, invested)],
                color=GREEN, alpha=0.12, interpolate=True)
ax.fill_between(dates, invested, value,
                where=[v < inv for v, inv in zip(value, invested)],
                color=RED, alpha=0.12, interpolate=True)

# Zero line for reference if pnl crosses zero
if min(value) < min(invested):
    pass  # already handled by fill_between

# Highlight today
ax.axvline(x=dates[-1], color=VIOLET, linewidth=1, linestyle=":", alpha=0.5)
ax.annotate(f"Today\n${final_val:,.0f}",
            xy=(dates[-1], final_val),
            xytext=(-55, 18), textcoords="offset points",
            fontsize=8, color=VIOLET,
            arrowprops=dict(arrowstyle="->", color=VIOLET, lw=1.2))

# Axes formatting
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right")
ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v:,.0f}"))

# Legend
legend_patches = [
    plt.Line2D([0], [0], color=VIOLET, linewidth=2.5, label="Portfolio Value"),
    plt.Line2D([0], [0], color=SLATE_500, linewidth=1.5, linestyle="--", label="Cumulative Invested"),
    mpatches.Patch(color=GREEN, alpha=0.3, label="Gain"),
    mpatches.Patch(color=RED,   alpha=0.3, label="Loss"),
]
ax.legend(handles=legend_patches, loc="upper left", fontsize=8.5,
          frameon=True, framealpha=0.9, edgecolor=SLATE_200)

# ── Footer ────────────────────────────────────────────────────────────────────
fig.text(0.055, 0.04,
         "Polymarket Trump Tracker · Paper Trading Portfolio · "
         f"Generated {datetime.now().strftime('%B %d, %Y')}",
         fontsize=8, color=SLATE_500)

import os
out_dir = os.path.join(os.path.dirname(__file__), "charts")
os.makedirs(out_dir, exist_ok=True)
out = os.path.join(out_dir, "gain_chart.png")
plt.savefig(out, dpi=180, bbox_inches="tight", facecolor="white")
print(f"Saved → {out}")
