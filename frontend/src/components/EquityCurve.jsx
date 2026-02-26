import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";

function formatDate(d) {
  const date = new Date(d + "T00:00:00");
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

// mode: "pro" | "anti" | "dual"
export default function EquityCurve({ curve, stats, antiCurve, antiStats, mode = "pro" }) {
  const activeCurve = mode === "anti" ? antiCurve : curve;
  const activeStats = mode === "anti" ? antiStats : stats;

  if (!activeCurve || activeCurve.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <h3 className="text-base font-semibold mb-2">P&L Equity Curve</h3>
        <p className="text-slate-500 text-sm py-4">
          No trade data available for equity curve.
        </p>
      </div>
    );
  }

  const data = activeCurve.map((pt, i) => {
    const point = {
      date: pt.date,
      pnl: pt.total_pnl,
      invested: pt.cumulative_invested,
      pnlPct: pt.cumulative_invested > 0
        ? +((pt.total_pnl / pt.cumulative_invested) * 100).toFixed(2)
        : 0,
    };
    // In dual mode, overlay the anti curve
    if (mode === "dual" && antiCurve) {
      const antiPt = antiCurve[i];
      if (antiPt) point.antiPnl = antiPt.total_pnl;
    }
    if (activeStats?.regression_slope != null && activeStats?.trend_significant) {
      const intercept = activeCurve[0].total_pnl;
      point.trend = +(activeStats.regression_slope * i + intercept).toFixed(4);
    }
    return point;
  });

  const title =
    mode === "anti"
      ? "P&L Equity Curve — Anti-Trump"
      : mode === "dual"
      ? "P&L Equity Curve — Pro vs Anti-Trump"
      : "P&L Equity Curve";

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4">
      <h3 className="text-base font-semibold mb-3">{title}</h3>
      <ResponsiveContainer width="100%" height={350}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            dataKey="date"
            tickFormatter={formatDate}
            tick={{ fontSize: 11 }}
            interval="preserveStartEnd"
          />
          {/* Left axis: P&L */}
          <YAxis
            yAxisId="pnl"
            tick={{ fontSize: 11 }}
            tickFormatter={(v) => `$${v.toFixed(0)}`}
          />
          {/* Right axis: Total Invested (only in non-dual mode) */}
          {mode !== "dual" && (
            <YAxis
              yAxisId="invested"
              orientation="right"
              tick={{ fontSize: 11, fill: "#93a3b8" }}
              tickFormatter={(v) => `$${v.toFixed(0)}`}
            />
          )}
          <Tooltip
            labelFormatter={formatDate}
            formatter={(v, name) => {
              if (name === "pnl") return [`$${v.toFixed(2)}`, mode === "dual" ? "Pro-Trump P&L" : "P&L"];
              if (name === "antiPnl") return [`$${v.toFixed(2)}`, "Anti-Trump P&L"];
              if (name === "invested") return [`$${v.toFixed(2)}`, "Total Invested"];
              if (name === "trend") return [`$${v.toFixed(2)}`, "Trend"];
              if (name === "pnlPct") return [`${v.toFixed(2)}%`, "P&L %"];
              return [v, name];
            }}
          />
          <Legend
            formatter={(value) => {
              if (value === "pnl") return mode === "dual" ? "Pro-Trump P&L" : "P&L";
              if (value === "antiPnl") return "Anti-Trump P&L";
              if (value === "invested") return "Total Invested";
              if (value === "pnlPct") return "P&L %";
              return "Trend";
            }}
          />
          <ReferenceLine yAxisId="pnl" y={0} stroke="#94a3b8" strokeDasharray="3 3" />

          {/* Main P&L line */}
          <Line
            yAxisId="pnl"
            type="monotone"
            dataKey="pnl"
            name="pnl"
            stroke={mode === "dual" ? "#16a34a" : "#16a34a"}
            dot={false}
            strokeWidth={2}
          />

          {/* Anti-Trump overlay in dual mode */}
          {mode === "dual" && (
            <Line
              yAxisId="pnl"
              type="monotone"
              dataKey="antiPnl"
              name="antiPnl"
              stroke="#ef4444"
              dot={false}
              strokeWidth={2}
              strokeDasharray="5 3"
            />
          )}

          {/* P&L % and Invested only in single-mode */}
          {mode !== "dual" && (
            <Line
              yAxisId="pnl"
              type="monotone"
              dataKey="pnlPct"
              name="pnlPct"
              stroke="#8b5cf6"
              dot={false}
              strokeWidth={1.5}
              strokeDasharray="4 3"
            />
          )}
          {mode !== "dual" && (
            <Line
              yAxisId="invested"
              type="monotone"
              dataKey="invested"
              name="invested"
              stroke="#3b82f6"
              dot={false}
              strokeWidth={1.5}
              strokeDasharray="5 5"
            />
          )}

          {activeStats?.trend_significant && mode !== "dual" && (
            <Line
              yAxisId="pnl"
              type="monotone"
              dataKey="trend"
              name="trend"
              stroke="#d97706"
              dot={false}
              strokeWidth={1.5}
              strokeDasharray="8 4"
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
