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

export default function EquityCurve({ curve, stats }) {
  if (!curve || curve.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <h3 className="text-base font-semibold mb-2">P&L Equity Curve</h3>
        <p className="text-slate-500 text-sm py-4">
          No trade data available for equity curve.
        </p>
      </div>
    );
  }

  const data = curve.map((pt, i) => {
    const point = {
      date: pt.date,
      pnl: pt.total_pnl,
      invested: pt.cumulative_invested,
      pnlPct: pt.cumulative_invested > 0
        ? +((pt.total_pnl / pt.cumulative_invested) * 100).toFixed(2)
        : 0,
    };
    if (stats?.regression_slope != null && stats?.trend_significant) {
      const intercept = curve[0].total_pnl;
      point.trend = +(stats.regression_slope * i + intercept).toFixed(4);
    }
    return point;
  });

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4">
      <h3 className="text-base font-semibold mb-3">P&L Equity Curve</h3>
      <ResponsiveContainer width="100%" height={350}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            dataKey="date"
            tickFormatter={formatDate}
            tick={{ fontSize: 11 }}
            interval="preserveStartEnd"
          />
          {/* Left axis: P&L (auto-scaled to show detail) */}
          <YAxis
            yAxisId="pnl"
            tick={{ fontSize: 11 }}
            tickFormatter={(v) => `$${v.toFixed(0)}`}
          />
          {/* Right axis: Total Invested */}
          <YAxis
            yAxisId="invested"
            orientation="right"
            tick={{ fontSize: 11, fill: "#93a3b8" }}
            tickFormatter={(v) => `$${v.toFixed(0)}`}
          />
          <Tooltip
            labelFormatter={formatDate}
            formatter={(v, name) => {
              if (name === "pnl") return [`$${v.toFixed(2)}`, "P&L"];
              if (name === "invested") return [`$${v.toFixed(2)}`, "Total Invested"];
              if (name === "trend") return [`$${v.toFixed(2)}`, "Trend"];
              if (name === "pnlPct") return [`${v.toFixed(2)}%`, "P&L %"];
              return [v, name];
            }}
          />
          <Legend
            formatter={(value) =>
              value === "pnl"
                ? "P&L"
                : value === "invested"
                  ? "Total Invested"
                  : value === "pnlPct"
                    ? "P&L %"
                    : "Trend"
            }
          />
          <ReferenceLine yAxisId="pnl" y={0} stroke="#94a3b8" strokeDasharray="3 3" />
          <Line
            yAxisId="pnl"
            type="monotone"
            dataKey="pnl"
            name="pnl"
            stroke="#16a34a"
            dot={false}
            strokeWidth={2}
          />
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
          {stats?.trend_significant && (
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
