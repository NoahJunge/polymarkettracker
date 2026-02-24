export default function PortfolioStats({ stats }) {
  if (!stats) return null;

  const cards = [
    {
      label: "Win Rate",
      value: stats.win_rate != null ? `${stats.win_rate}%` : "--",
      sub: `${stats.total_wins}W / ${stats.total_losses}L`,
    },
    {
      label: "Profit Factor",
      value: stats.profit_factor != null ? stats.profit_factor.toFixed(2) : "--",
      sub: stats.profit_factor != null
        ? stats.profit_factor >= 1.5
          ? "Good"
          : stats.profit_factor >= 1.0
            ? "Marginal"
            : "Poor"
        : "",
    },
    {
      label: "Sharpe Ratio",
      value: stats.sharpe_ratio != null ? stats.sharpe_ratio.toFixed(2) : "--",
      sub: "Daily risk-adjusted",
    },
    {
      label: "Max Drawdown",
      value: stats.max_drawdown != null ? `$${stats.max_drawdown.toFixed(2)}` : "--",
      sub: "Peak to trough",
    },
    {
      label: "Avg Win",
      value: stats.avg_win != null ? `$${stats.avg_win.toFixed(2)}` : "--",
      sub: `${stats.total_wins} winning trades`,
    },
    {
      label: "Avg Loss",
      value: stats.avg_loss != null ? `$${stats.avg_loss.toFixed(2)}` : "--",
      sub: `${stats.total_losses} losing trades`,
    },
  ];

  // Trend significance banner
  let trendBg = "bg-slate-50 border-slate-200";
  let trendText = "text-slate-600";
  let trendLabel = "No significant trend detected";
  if (stats.trend_significant) {
    if (stats.trend_direction === "up") {
      trendBg = "bg-green-50 border-green-200";
      trendText = "text-green-700";
      trendLabel = "Significant upward trend detected";
    } else if (stats.trend_direction === "down") {
      trendBg = "bg-red-50 border-red-200";
      trendText = "text-red-700";
      trendLabel = "Significant downward trend detected";
    }
  }

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4">
      <h3 className="text-base font-semibold mb-3">Portfolio Statistics</h3>

      {/* Trend banner */}
      <div className={`rounded-lg border p-3 mb-4 ${trendBg}`}>
        <p className={`text-sm font-medium ${trendText}`}>{trendLabel}</p>
        {stats.regression_r_squared != null && (
          <p className="text-xs text-slate-500 mt-1">
            R² = {stats.regression_r_squared.toFixed(4)} | p-value ={" "}
            {stats.regression_p_value != null
              ? stats.regression_p_value < 0.001
                ? "<0.001"
                : stats.regression_p_value.toFixed(4)
              : "--"}
            {stats.regression_slope != null && (
              <> | Slope = {stats.regression_slope.toFixed(4)}/day</>
            )}
          </p>
        )}
      </div>

      {/* Stat cards grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {cards.map((c) => (
          <div
            key={c.label}
            className="bg-slate-50 rounded-lg p-3 text-center"
          >
            <p className="text-xs text-slate-500 mb-1">{c.label}</p>
            <p className="text-lg font-semibold text-slate-900">{c.value}</p>
            {c.sub && (
              <p className="text-xs text-slate-400 mt-0.5">{c.sub}</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
