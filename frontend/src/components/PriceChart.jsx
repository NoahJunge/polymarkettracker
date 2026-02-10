import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

function formatTimestamp(ts) {
  const d = new Date(ts);
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function PriceChart({ snapshots }) {
  if (!snapshots || snapshots.length === 0) {
    return <p className="text-slate-500 py-4">No snapshot data available.</p>;
  }

  const data = snapshots
    .slice()
    .sort((a, b) => new Date(a.timestamp_utc) - new Date(b.timestamp_utc))
    .map((s) => ({
      time: s.timestamp_utc,
      yes: +(s.yes_price * 100).toFixed(1),
      no: +(s.no_price * 100).toFixed(1),
    }));

  return (
    <ResponsiveContainer width="100%" height={350}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis
          dataKey="time"
          tickFormatter={formatTimestamp}
          tick={{ fontSize: 11 }}
          interval="preserveStartEnd"
        />
        <YAxis
          domain={[0, 100]}
          tick={{ fontSize: 11 }}
          tickFormatter={(v) => `${v}¢`}
        />
        <Tooltip
          labelFormatter={formatTimestamp}
          formatter={(v) => [`${v}¢`]}
        />
        <Legend />
        <Line
          type="monotone"
          dataKey="yes"
          name="Yes"
          stroke="#16a34a"
          dot={false}
          strokeWidth={2}
        />
        <Line
          type="monotone"
          dataKey="no"
          name="No"
          stroke="#dc2626"
          dot={false}
          strokeWidth={2}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
