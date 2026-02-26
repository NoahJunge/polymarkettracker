import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Cell,
} from "recharts";

function formatDate(d) {
  const date = new Date(d + "T00:00:00");
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export default function DailyUnrealizedChart({ curve }) {
  if (!curve || curve.length === 0) return null;

  const data = curve.map((pt) => ({
    date: pt.date,
    unrealized: pt.unrealized_pnl,
  }));

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4">
      <h3 className="text-base font-semibold mb-3">Daily Unrealized Return</h3>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            dataKey="date"
            tickFormatter={formatDate}
            tick={{ fontSize: 10 }}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fontSize: 11 }}
            tickFormatter={(v) => `$${v.toFixed(0)}`}
          />
          <Tooltip
            labelFormatter={formatDate}
            formatter={(v) => [`$${v.toFixed(2)}`, "Unrealized P&L"]}
          />
          <ReferenceLine y={0} stroke="#94a3b8" strokeDasharray="3 3" />
          <Bar dataKey="unrealized" name="Unrealized P&L" maxBarSize={16}>
            {data.map((entry, index) => (
              <Cell
                key={index}
                fill={entry.unrealized >= 0 ? "#16a34a" : "#dc2626"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
