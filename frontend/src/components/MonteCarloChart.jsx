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

export default function MonteCarloChart({ result }) {
  if (!result) return null;

  const data = result.histogram.map((bin) => ({
    label: bin.bin_start.toFixed(1),
    count: bin.count,
    positive: bin.bin_start >= 0,
    bin_start: bin.bin_start,
    bin_end: bin.bin_end,
  }));

  const probPct = (result.prob_positive * 100).toFixed(1);
  const isGaining = result.prob_positive >= 0.5;

  return (
    <div className="bg-slate-50 rounded-lg border border-slate-200 p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-1">
        <h4 className="text-sm font-semibold text-slate-800">
          {result.percentage}% of markets
          <span className="ml-1.5 text-xs font-normal text-slate-500">
            (~{result.markets_sampled} of {result.total_markets})
          </span>
        </h4>
        <span
          className={`text-sm font-semibold ${
            isGaining ? "text-green-600" : "text-red-600"
          }`}
        >
          P(gain) = {probPct}%
        </span>
      </div>

      {/* Histogram */}
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={data} margin={{ top: 4, right: 4, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 9 }}
            interval={Math.floor(data.length / 5)}
            tickFormatter={(v) => `$${parseFloat(v).toFixed(0)}`}
          />
          <YAxis tick={{ fontSize: 10 }} />
          <Tooltip
            formatter={(v) => [v, "Outcomes"]}
            labelFormatter={(label, payload) => {
              if (!payload || !payload[0]) return `$${label}`;
              const d = payload[0].payload;
              return `$${parseFloat(d.bin_start).toFixed(1)} – $${parseFloat(d.bin_end).toFixed(1)}`;
            }}
          />
          <ReferenceLine x="0.0" stroke="#94a3b8" />
          <Bar dataKey="count" name="Outcomes" maxBarSize={20}>
            {data.map((entry, index) => (
              <Cell
                key={index}
                fill={entry.positive ? "#16a34a" : "#dc2626"}
                fillOpacity={0.75}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* Stats grid */}
      <div className="grid grid-cols-4 gap-2 mt-3 text-center">
        <div>
          <p className="text-xs text-slate-500">Expected P&L</p>
          <p
            className={`text-sm font-semibold ${
              result.mean >= 0 ? "text-green-600" : "text-red-600"
            }`}
          >
            {result.mean >= 0 ? "+" : ""}${result.mean.toFixed(2)}
          </p>
        </div>
        <div>
          <p className="text-xs text-slate-500">Median</p>
          <p
            className={`text-sm font-semibold ${
              result.median >= 0 ? "text-green-600" : "text-red-600"
            }`}
          >
            {result.median >= 0 ? "+" : ""}${result.median.toFixed(2)}
          </p>
        </div>
        <div>
          <p className="text-xs text-slate-500">5th–95th pct</p>
          <p className="text-sm font-semibold text-slate-700">
            ${result.p5.toFixed(0)} – ${result.p95.toFixed(0)}
          </p>
        </div>
        <div>
          <p className="text-xs text-slate-500">Std Dev</p>
          <p className="text-sm font-semibold text-slate-700">
            ${result.std.toFixed(2)}
          </p>
        </div>
      </div>
    </div>
  );
}
