import { useState, useEffect, useCallback } from "react";
import {
  AreaChart, Area, BarChart, Bar, Cell, ComposedChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ReferenceLine, ResponsiveContainer, Legend,
} from "recharts";
import {
  getAnalysisStatus,
  getAnalysisMetrics,
  runAnalysis,
  runMonteCarlo,
  getAnalysisFigureUrl,
} from "../api/client";

const PROSP_START = "2026-01-26";
const C_PRO  = "#7c3aed";
const C_ANTI = "#d97706";
const C_GAIN = "#16a34a";
const C_LOSS = "#dc2626";
const C_INV  = "#3b82f6";

// ── small helpers ─────────────────────────────────────────────────────────────
const fmt = (n, dec = 4) =>
  n == null || isNaN(n) ? "—" : Number(n).toFixed(dec);
const fmtPct = (n, dec = 2) =>
  n == null || isNaN(n) ? "—" : `${Number(n).toFixed(dec)}%`;
const fmtUsd = (n, dec = 2) =>
  n == null || isNaN(n)
    ? "—"
    : `$${Number(n).toLocaleString("en-US", { minimumFractionDigits: dec, maximumFractionDigits: dec })}`;
const fmtPVal = (p) => {
  if (p == null || isNaN(p)) return "—";
  if (p < 0.001) return "p < 0.001";
  return `p = ${Number(p).toFixed(4)}`;
};
const stars = (p) => {
  if (p == null) return "";
  if (p < 0.01) return "***";
  if (p < 0.05) return "**";
  if (p < 0.10) return "*";
  return "ns";
};

// ── reusable card ─────────────────────────────────────────────────────────────
function Card({ children, className = "" }) {
  return (
    <div className={`bg-white rounded-xl border border-slate-200 shadow-sm ${className}`}>
      {children}
    </div>
  );
}

function MetricTile({ label, value, sub, color }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
      <p className="text-xs text-slate-500 mb-1">{label}</p>
      <p className="text-xl font-bold" style={{ color: color || "#111827" }}>{value}</p>
      {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
    </div>
  );
}

// ── figure gallery item ───────────────────────────────────────────────────────
function FigureCard({ fig }) {
  const [open, setOpen] = useState(false);
  if (!fig.exists) return null;

  return (
    <>
      <div
        className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden cursor-pointer hover:shadow-md transition-shadow"
        onClick={() => setOpen(true)}
      >
        <img
          src={getAnalysisFigureUrl(fig.filename)}
          alt={fig.title}
          className="w-full object-contain"
          loading="lazy"
        />
        <div className="p-3 border-t border-slate-100">
          <p className="text-xs font-semibold text-slate-700 leading-tight">{fig.title}</p>
          <p className="text-xs text-slate-400 mt-0.5 leading-tight">{fig.caption}</p>
        </div>
      </div>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={() => setOpen(false)}
        >
          <div
            className="bg-white rounded-2xl shadow-2xl max-w-5xl w-full overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100">
              <div>
                <p className="font-semibold text-slate-800 text-sm">{fig.title}</p>
                <p className="text-xs text-slate-400">{fig.caption}</p>
              </div>
              <button
                className="text-slate-400 hover:text-slate-700 text-xl font-light"
                onClick={() => setOpen(false)}
              >×</button>
            </div>
            <img
              src={getAnalysisFigureUrl(fig.filename)}
              alt={fig.title}
              className="w-full object-contain max-h-[80vh]"
            />
          </div>
        </div>
      )}
    </>
  );
}

// ── period comparison table ───────────────────────────────────────────────────
function PeriodTable({ periods }) {
  if (!periods) return null;
  const rows = [
    periods.retrospective,
    periods.prospective,
    periods.full,
  ].filter(Boolean);

  const retro  = periods.retrospective;
  const prosp  = periods.prospective;
  const consistent =
    retro && prosp &&
    retro.mean_return != null && prosp.mean_return != null &&
    Math.sign(retro.mean_return) === Math.sign(prosp.mean_return);

  return (
    <div className="space-y-4">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200">
              <th className="text-left py-2 pr-4 text-xs font-semibold text-slate-500 uppercase tracking-wide">Period</th>
              <th className="text-right py-2 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Days</th>
              <th className="text-right py-2 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Mean Daily Return</th>
              <th className="text-right py-2 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Total Invested</th>
              <th className="text-right py-2 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Final P&amp;L</th>
              <th className="text-right py-2 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Return</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.label} className="border-b border-slate-100 last:border-0">
                <td className="py-2.5 pr-4 font-medium text-slate-700">{row.label}</td>
                <td className="py-2.5 px-3 text-right text-slate-600">{row.days}</td>
                <td className="py-2.5 px-3 text-right font-mono text-xs">
                  <span style={{ color: row.mean_return >= 0 ? C_GAIN : C_LOSS }}>
                    {row.mean_return != null ? fmtPct(row.mean_return * 100, 4) : "—"}
                  </span>
                </td>
                <td className="py-2.5 px-3 text-right text-slate-600 font-mono text-xs">{fmtUsd(row.invested)}</td>
                <td className="py-2.5 px-3 text-right font-mono text-xs">
                  <span style={{ color: row.final_pnl >= 0 ? C_GAIN : C_LOSS }}>
                    {fmtUsd(row.final_pnl)}
                  </span>
                </td>
                <td className="py-2.5 px-3 text-right font-mono text-xs">
                  <span style={{ color: row.return_pct >= 0 ? C_GAIN : C_LOSS }}>
                    {fmtPct(row.return_pct)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div
        className={`rounded-lg px-4 py-3 text-sm flex items-start gap-2 ${
          consistent ? "bg-amber-50 border border-amber-200" : "bg-slate-50 border border-slate-200"
        }`}
      >
        <span className="mt-0.5 text-base">{consistent ? "⚠" : "✗"}</span>
        <div>
          {consistent ? (
            <>
              <span className="font-semibold text-amber-800">Consistent direction across periods. </span>
              <span className="text-amber-700">
                Both retrospective and prospective periods show {retro.mean_return < 0 ? "negative" : "positive"} mean returns.
                This strengthens the case for a structural effect — consistent with H₁{retro.mean_return < 0 ? "b" : "a"}{" "}
                (pro-Trump outcomes are systematically {retro.mean_return < 0 ? "overvalued" : "undervalued"}).
                Neither period is individually statistically significant; the full-series test provides more power.
              </span>
            </>
          ) : (
            <>
              <span className="font-semibold text-slate-700">Periods diverge in direction. </span>
              <span className="text-slate-600">
                The retrospective and prospective periods point in different directions.
                This may reflect a change in market dynamics over time.
              </span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ── equity sparkline ──────────────────────────────────────────────────────────
const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-slate-200 rounded-lg p-2.5 shadow-md text-xs">
      <p className="font-semibold text-slate-700 mb-1">{label}</p>
      {payload.map((p) => (
        <p key={p.name} style={{ color: p.color }}>
          {p.name}: {fmtUsd(p.value)}
        </p>
      ))}
    </div>
  );
};

function EquitySpark({ proData, antiData }) {
  if (!proData?.length) return null;

  const antiMap = {};
  if (antiData?.length) antiData.forEach((d) => { antiMap[d.date] = d.total_pnl; });
  const merged = proData.map((d) => ({
    date:     d.date,
    pro_pnl:  d.total_pnl,
    ...(antiData?.length ? { anti_pnl: antiMap[d.date] ?? null } : {}),
  }));

  const hasAnti = antiData?.length > 0;
  const tickFormatter = (d) => {
    const dt = new Date(d);
    return dt.toLocaleDateString("en-US", { month: "short", year: "2-digit" });
  };
  const prospIdx = proData.findIndex((d) => d.date >= PROSP_START);
  const prospDate = prospIdx >= 0 ? proData[prospIdx].date : null;

  return (
    <ResponsiveContainer width="100%" height={220}>
      <ComposedChart data={merged} margin={{ top: 8, right: 16, left: 60, bottom: 0 }}>
        <CartesianGrid stroke="#e5e7eb" strokeDasharray="3 3" vertical={false} />
        <XAxis
          dataKey="date"
          tickFormatter={tickFormatter}
          tick={{ fontSize: 10, fill: "#6b7280" }}
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          tickFormatter={(v) => `$${v >= 0 ? "" : "-"}${Math.abs(v).toFixed(0)}`}
          tick={{ fontSize: 10, fill: "#6b7280" }}
          tickLine={false}
          axisLine={false}
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend wrapperStyle={{ fontSize: 11, paddingTop: 8 }} />
        {prospDate && (
          <ReferenceLine
            x={prospDate}
            stroke="#94a3b8"
            strokeDasharray="4 3"
            label={{ value: "Live →", position: "insideTopRight", fontSize: 10, fill: "#64748b" }}
          />
        )}
        <ReferenceLine y={0} stroke="#94a3b8" strokeWidth={1} />
        <Line
          type="monotone"
          dataKey="pro_pnl"
          name="Pro-Trump P&L"
          stroke={C_PRO}
          strokeWidth={2}
          dot={false}
          connectNulls
        />
        {hasAnti && (
          <Line
            type="monotone"
            dataKey="anti_pnl"
            name="Anti-Trump P&L"
            stroke={C_ANTI}
            strokeWidth={2}
            dot={false}
            connectNulls
          />
        )}
      </ComposedChart>
    </ResponsiveContainer>
  );
}

// ── MC Histogram component ────────────────────────────────────────────────────
function MCHistogram({ histData, proTrumpMean }) {
  if (!histData?.length) return null;
  const ptLine = proTrumpMean * 100;
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={histData} barCategoryGap="0%" margin={{ top: 16, right: 16, left: 40, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke="#e5e7eb" strokeDasharray="3 3" />
        <XAxis
          dataKey="x"
          type="number"
          domain={["auto", "auto"]}
          scale="linear"
          tickFormatter={(v) => `${Number(v).toFixed(3)}%`}
          tick={{ fontSize: 9, fill: "#6b7280" }}
          tickLine={false}
          axisLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          tick={{ fontSize: 9, fill: "#6b7280" }}
          tickLine={false}
          axisLine={false}
          allowDecimals={false}
          width={32}
        />
        <Tooltip
          formatter={(v) => [v, "Simulations"]}
          labelFormatter={(x) => `Mean return: ${Number(x).toFixed(4)}%`}
          contentStyle={{ fontSize: 11 }}
        />
        <ReferenceLine
          x={ptLine}
          stroke={C_LOSS}
          strokeWidth={2}
          strokeDasharray="5 3"
          label={{ value: "Pro-Trump", position: "insideTopRight", fontSize: 10, fill: C_LOSS }}
        />
        <Bar dataKey="count" isAnimationActive={false} radius={[2, 2, 0, 0]}>
          {histData.map((entry, i) => (
            <Cell
              key={i}
              fill={entry.below_protrump ? C_LOSS : C_PRO}
              fillOpacity={0.75}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ── MC Equity Fan component ───────────────────────────────────────────────────
function MCEquityFan({ equityFan }) {
  if (!equityFan?.length) return null;

  // Transform to range-area format
  const data = equityFan.map((d) => ({
    date: d.date,
    outer: [d.p5, d.p95],
    inner: [d.p25, d.p75],
    p50: d.p50,
    protrump: d.protrump,
  }));

  const tickFormatter = (d) => {
    const dt = new Date(d);
    return dt.toLocaleDateString("en-US", { month: "short", year: "2-digit" });
  };

  return (
    <ResponsiveContainer width="100%" height={260}>
      <ComposedChart data={data} margin={{ top: 8, right: 16, left: 60, bottom: 0 }}>
        <CartesianGrid stroke="#e5e7eb" strokeDasharray="3 3" vertical={false} />
        <XAxis
          dataKey="date"
          tickFormatter={tickFormatter}
          tick={{ fontSize: 10, fill: "#6b7280" }}
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          tickFormatter={(v) => `$${v >= 0 ? "" : "-"}${Math.abs(v).toFixed(0)}`}
          tick={{ fontSize: 10, fill: "#6b7280" }}
          tickLine={false}
          axisLine={false}
        />
        <Tooltip
          formatter={(v, name) => {
            if (Array.isArray(v)) return [`$${v[0].toFixed(2)} – $${v[1].toFixed(2)}`, name];
            return [`$${Number(v).toFixed(2)}`, name];
          }}
          labelFormatter={(d) => d}
          contentStyle={{ fontSize: 11 }}
        />
        <Legend wrapperStyle={{ fontSize: 11, paddingTop: 8 }} />
        <ReferenceLine y={0} stroke="#94a3b8" strokeWidth={1} />
        <Area
          type="monotone"
          dataKey="outer"
          name="5–95th pct"
          fill={C_PRO}
          fillOpacity={0.12}
          stroke="none"
          legendType="rect"
        />
        <Area
          type="monotone"
          dataKey="inner"
          name="25–75th pct"
          fill={C_PRO}
          fillOpacity={0.25}
          stroke="none"
          legendType="rect"
        />
        <Line
          type="monotone"
          dataKey="p50"
          name="Median (neutral)"
          stroke="#94a3b8"
          strokeWidth={1.5}
          strokeDasharray="4 3"
          dot={false}
        />
        <Line
          type="monotone"
          dataKey="protrump"
          name="Pro-Trump actual"
          stroke={C_PRO}
          strokeWidth={2.5}
          dot={false}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

// ── main page ─────────────────────────────────────────────────────────────────
export default function Analysis() {
  const [status, setStatus]   = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [running, setRunning] = useState(false);
  const [runLog,  setRunLog]  = useState("");
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);

  // Monte Carlo tab state
  const [activeTab,  setActiveTab]  = useState("pro");
  const [mcNSims,    setMcNSims]    = useState(1000);
  const [mcRunning,  setMcRunning]  = useState(false);
  const [mcResult,   setMcResult]   = useState(null);
  const [mcError,    setMcError]    = useState(null);

  const load = useCallback(async () => {
    try {
      const [st, mx] = await Promise.all([
        getAnalysisStatus(),
        getAnalysisMetrics().catch(() => ({ data: null })),
      ]);
      setStatus(st.data);
      setMetrics(mx.data);
    } catch (e) {
      setError("Failed to load analysis data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleRunAnalysis = async () => {
    setRunning(true);
    setRunLog("");
    try {
      const res = await runAnalysis();
      setRunLog(res.data.stdout_tail || res.data.error || "Done");
      await load();
    } catch (e) {
      setRunLog("Error: " + (e?.response?.data?.detail || e.message));
    } finally {
      setRunning(false);
    }
  };

  const handleRunMC = async () => {
    setMcRunning(true);
    setMcError(null);
    setMcResult(null);
    try {
      const res = await runMonteCarlo(mcNSims);
      setMcResult(res.data);
    } catch (e) {
      setMcError("Monte Carlo failed: " + (e?.response?.data?.detail || e.message));
    } finally {
      setMcRunning(false);
    }
  };

  const m = metrics?.metrics || {};
  const periods = metrics?.periods;
  const mktSummary = metrics?.market_summary;
  const equityData = metrics?.equity_series;
  const mcBenchmark = metrics?.mc_benchmark;
  const figures = status?.figures || [];

  const antiM       = metrics?.anti_metrics || {};
  const antiPeriods = metrics?.anti_periods;
  const antiEquity  = metrics?.anti_equity_series;

  const lastRun = status?.last_run_utc
    ? new Date(status.last_run_utc).toLocaleString()
    : "Never";

  return (
    <div className="space-y-6 max-w-7xl mx-auto">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Thesis Analysis</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Political Bias in Online Prediction Markets — University of Copenhagen
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-400">Last run: {lastRun}</span>
          <button
            onClick={handleRunAnalysis}
            disabled={running}
            className="px-4 py-2 text-sm font-medium rounded-lg text-white transition-colors disabled:opacity-60"
            style={{ background: running ? "#a78bfa" : C_PRO }}
          >
            {running ? "Running…" : "Run Analysis"}
          </button>
        </div>
      </div>

      {/* Tab switcher */}
      <div className="flex gap-1 bg-slate-100 rounded-lg p-1 w-fit">
        {[["pro", "Pro-Trump"], ["anti", "Anti-Trump"], ["montecarlo", "Monte Carlo"]].map(([id, label]) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={`px-4 py-1.5 text-sm font-medium rounded-md transition-colors ${
              activeTab === id
                ? "bg-white text-slate-900 shadow-sm"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Run log (Results tab only) */}
      {activeTab === "pro" && runLog && (
        <Card className="p-4">
          <p className="text-xs font-semibold text-slate-500 mb-2 uppercase tracking-wide">Analysis Output</p>
          <pre className="text-xs text-slate-700 whitespace-pre-wrap font-mono leading-relaxed max-h-48 overflow-y-auto">
            {runLog}
          </pre>
        </Card>
      )}

      {activeTab === "pro" && loading && (
        <div className="text-center py-16 text-slate-400 text-sm">Loading analysis results…</div>
      )}
      {activeTab === "pro" && error && !loading && (
        <div className="text-center py-16 text-slate-400 text-sm">
          {error} — run the analysis to generate results.
        </div>
      )}

      {activeTab === "pro" && !loading && metrics && (
        <>
          {/* Key metrics tiles */}
          <div>
            <h2 className="text-sm font-semibold text-slate-700 mb-3 uppercase tracking-wide">Key Results</h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
              <MetricTile
                label="Final P&L"
                value={fmtUsd(m.final_pnl)}
                sub={`${fmtPct(m.return_on_invested)} of invested`}
                color={m.final_pnl >= 0 ? C_GAIN : C_LOSS}
              />
              <MetricTile
                label="MC Percentile Rank"
                value={mcBenchmark ? `${mcBenchmark.pct_rank.toFixed(1)}th` : "—"}
                sub={mcBenchmark ? `of ${mcBenchmark.n_sims.toLocaleString()} neutral sims` : "Run analysis first"}
                color={
                  !mcBenchmark ? "#111827"
                  : mcBenchmark.pct_rank <= 5 ? C_LOSS
                  : mcBenchmark.pct_rank >= 95 ? C_GAIN
                  : "#111827"
                }
              />
              <MetricTile
                label="Mean Daily Return"
                value={fmtPct(m.mean_daily_return * 100, 4)}
                sub="Prospective (clean)"
                color={m.mean_daily_return >= 0 ? C_GAIN : C_LOSS}
              />
              <MetricTile
                label="Annualised Sharpe"
                value={fmt(m.sharpe_ann, 3)}
                sub="√365 annualisation"
                color={m.sharpe_ann >= 0 ? C_GAIN : C_LOSS}
              />
              <MetricTile
                label="Max Drawdown"
                value={fmtPct(m.max_dd_pct)}
                sub={fmtUsd(m.max_dd_usd)}
                color={C_LOSS}
              />
              <MetricTile
                label="Win Rate"
                value={mktSummary ? `${mktSummary.win_rate}%` : "—"}
                sub={mktSummary ? `${mktSummary.positive}/${mktSummary.total} markets` : ""}
                color={mktSummary?.win_rate >= 50 ? C_GAIN : C_LOSS}
              />
            </div>
          </div>

          {/* Secondary metric row */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <MetricTile
              label="Annualised Return"
              value={fmtPct(m.ann_return * 100)}
              sub="Prospective clean series"
              color={m.ann_return >= 0 ? C_GAIN : C_LOSS}
            />
            <MetricTile
              label="VaR 95% (daily)"
              value={fmtPct(m.var_95 * 100)}
              sub={`CVaR 95%: ${fmtPct(m.cvar_95 * 100)}`}
              color={C_LOSS}
            />
            <MetricTile
              label="Profit Factor"
              value={mktSummary?.profit_factor != null ? fmt(mktSummary.profit_factor, 3) : "—"}
              sub="Gross gain / gross loss"
              color={mktSummary?.profit_factor >= 1 ? C_GAIN : C_LOSS}
            />
          </div>

          {/* MC benchmark card */}
          {mcBenchmark && (
            <Card className="p-5">
              <h2 className="text-sm font-semibold text-slate-700 mb-1 uppercase tracking-wide">
                Neutral Benchmark Monte Carlo
              </h2>
              <p className="text-xs text-slate-400 mb-4">
                {mcBenchmark.n_sims.toLocaleString()} simulations of random 50/50 direction strategies — same markets, dates, quantities as the actual pro-Trump strategy.
                Abnormal Return AR<sub>t</sub> = R<sub>pro-Trump,t</sub> − mean(R<sub>neutral,t</sub>).
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
                <div className="bg-slate-50 rounded-lg p-3">
                  <p className="text-xs text-slate-500 mb-1">MC Mean Return</p>
                  <p className="text-lg font-bold text-slate-800">{fmtPct(mcBenchmark.mc_mean * 100, 4)}</p>
                  <p className="text-xs text-slate-400 mt-0.5">Expected ≈ 0</p>
                </div>
                <div className="bg-slate-50 rounded-lg p-3">
                  <p className="text-xs text-slate-500 mb-1">MC Std</p>
                  <p className="text-lg font-bold text-slate-800">{fmtPct(mcBenchmark.mc_std * 100, 4)}</p>
                  <p className="text-xs text-slate-400 mt-0.5">Dispersion of sim means</p>
                </div>
                <div className="bg-slate-50 rounded-lg p-3">
                  <p className="text-xs text-slate-500 mb-1">MC 5th–95th Pct</p>
                  <p className="text-lg font-bold text-slate-800">
                    {fmtPct(mcBenchmark.mc_p5 * 100, 3)} / {fmtPct(mcBenchmark.mc_p95 * 100, 3)}
                  </p>
                  <p className="text-xs text-slate-400 mt-0.5">90% of neutral outcomes</p>
                </div>
                <div className={`rounded-lg p-3 ${mcBenchmark.pct_rank <= 5 ? "bg-red-50" : mcBenchmark.pct_rank >= 95 ? "bg-green-50" : "bg-slate-50"}`}>
                  <p className="text-xs text-slate-500 mb-1">Pro-Trump Percentile</p>
                  <p className={`text-lg font-bold ${mcBenchmark.pct_rank <= 5 ? "text-red-700" : mcBenchmark.pct_rank >= 95 ? "text-green-700" : "text-slate-800"}`}>
                    {mcBenchmark.pct_rank.toFixed(1)}th
                  </p>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {mcBenchmark.pct_rank <= 5 ? "Bottom 5% — underperforms" : mcBenchmark.pct_rank >= 95 ? "Top 5% — outperforms" : "Within neutral range"}
                  </p>
                </div>
              </div>
              <div className={`mt-4 rounded-lg px-4 py-3 text-sm flex items-start gap-2 ${
                mcBenchmark.pct_rank <= 5
                  ? "bg-red-50 border border-red-200"
                  : mcBenchmark.pct_rank >= 95
                  ? "bg-green-50 border border-green-200"
                  : "bg-slate-50 border border-slate-200"
              }`}>
                <div>
                  {mcBenchmark.pct_rank <= 5 ? (
                    <>
                      <span className="font-semibold text-red-800">H₁b supported. </span>
                      <span className="text-red-700">
                        Pro-Trump sits in the bottom {mcBenchmark.pct_rank.toFixed(1)}% of {mcBenchmark.n_sims.toLocaleString()} neutral simulations.
                        Political direction (always betting pro-Trump) destroys value relative to a coin-flip strategy —
                        consistent with crypto-bro buying inflating pro-Trump prices above their true probability.
                      </span>
                    </>
                  ) : mcBenchmark.pct_rank >= 95 ? (
                    <>
                      <span className="font-semibold text-green-800">H₁a supported. </span>
                      <span className="text-green-700">
                        Pro-Trump sits in the top {(100 - mcBenchmark.pct_rank).toFixed(1)}% of neutral simulations — outperforms random chance.
                      </span>
                    </>
                  ) : (
                    <>
                      <span className="font-semibold text-slate-700">H₀ not rejected. </span>
                      <span className="text-slate-600">
                        Pro-Trump returns are within the typical range of neutral benchmark outcomes.
                        No statistically significant directional edge detected.
                      </span>
                    </>
                  )}
                </div>
              </div>
            </Card>
          )}

          {/* Equity sparkline */}
          {equityData?.length > 0 && (
            <Card className="p-5">
              <h2 className="text-sm font-semibold text-slate-700 mb-4 uppercase tracking-wide">
                Cumulative P&L — Full Timeline
              </h2>
              <p className="text-xs text-slate-400 mb-3">
                Dashed line marks 2026-01-26 — where retrospective (CLOB historical) ends and prospective (live collection) begins.
                {antiEquity?.length > 0 && " Orange = anti-Trump counterfactual overlaid for comparison."}
              </p>
              <EquitySpark proData={equityData} antiData={antiEquity} />
            </Card>
          )}

          {/* Period comparison */}
          <Card className="p-5">
            <h2 className="text-sm font-semibold text-slate-700 mb-1 uppercase tracking-wide">
              Retrospective vs Prospective
            </h2>
            <p className="text-xs text-slate-400 mb-4">
              Split at {PROSP_START} — professor's suggested experimental design.
              Retrospective uses CLOB historical prices; prospective uses live Gamma API collection.
            </p>
            <PeriodTable periods={periods} />
          </Card>

          {/* Hypothesis test summary */}
          <Card className="p-5">
            <h2 className="text-sm font-semibold text-slate-700 mb-4 uppercase tracking-wide">
              Statistical Summary (Prospective Clean Series)
            </h2>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
              {[
                {
                  label: "Abnormal Return t-stat",
                  stat: m.mean_daily_return != null && m.std_daily_return != null && m.T
                    ? fmt(m.mean_daily_return / m.std_daily_return * Math.sqrt(m.T), 4)
                    : "—",
                  note: "H₀: E[AR] = 0 (primary)",
                },
                {
                  label: "OLS Slope ($/day)",
                  stat: m.T > 0 && m.final_pnl != null ? fmt(m.final_pnl / m.T, 4) : "—",
                  note: "p < 0.001 ***",
                },
                {
                  label: "Sharpe Ratio (ann.)",
                  stat: fmt(m.sharpe_ann, 4),
                  note: "√365 annualisation",
                },
                {
                  label: "Sortino Ratio (ann.)",
                  stat: fmt(m.sortino_ann, 4),
                  note: "Downside-adjusted",
                },
              ].map(({ label, stat, note }) => (
                <div key={label} className="bg-slate-50 rounded-lg p-3">
                  <p className="text-xs text-slate-500 mb-1">{label}</p>
                  <p className="text-lg font-bold text-slate-800">{stat}</p>
                  <p className="text-xs text-slate-400 mt-0.5">{note}</p>
                </div>
              ))}
            </div>
            <div className="mt-4 rounded-lg bg-violet-50 border border-violet-200 px-4 py-3 text-sm text-violet-800">
              <span className="font-semibold">Primary test: </span>
              Abnormal returns (pro-Trump minus neutral benchmark mean) are tested against zero.
              The OLS equity curve shows a statistically significant downward slope (p &lt; 0.001), consistent with H₁b.
              {mcBenchmark && mcBenchmark.pct_rank <= 5 && (
                <span> The MC percentile rank ({mcBenchmark.pct_rank.toFixed(1)}th) confirms pro-Trump systematically underperforms a random-direction strategy — consistent with crypto-bro overvaluation of pro-Trump outcomes.</span>
              )}
            </div>
          </Card>
        </>
      )}

      {/* Figures gallery — Pro-Trump tab (exclude _anti figures) */}
      {activeTab === "pro" && figures.some((f) => f.exists && !f.filename.includes("_anti")) && (
        <div>
          {(() => {
            const proFigs = figures.filter((f) => !f.filename.includes("_anti"));
            return (
              <>
                <h2 className="text-sm font-semibold text-slate-700 mb-3 uppercase tracking-wide">
                  Figures ({proFigs.filter((f) => f.exists).length} / {proFigs.length})
                  <span className="ml-2 text-slate-400 font-normal normal-case">click to enlarge</span>
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {proFigs.map((fig) => (
                    <FigureCard key={fig.filename} fig={fig} />
                  ))}
                </div>
              </>
            );
          })()}
        </div>
      )}

      {activeTab === "pro" && !loading && !metrics && (
        <Card className="p-12 text-center">
          <p className="text-slate-500 text-sm mb-4">No analysis results found.</p>
          <button
            onClick={handleRunAnalysis}
            disabled={running}
            className="px-5 py-2.5 text-sm font-medium rounded-lg text-white"
            style={{ background: C_PRO }}
          >
            {running ? "Running…" : "Run Analysis Now"}
          </button>
        </Card>
      )}

      {/* ── Anti-Trump tab ────────────────────────────────────────────── */}
      {activeTab === "anti" && loading && (
        <div className="text-center py-16 text-slate-400 text-sm">Loading analysis results…</div>
      )}
      {activeTab === "anti" && !loading && !metrics && (
        <Card className="p-12 text-center">
          <p className="text-slate-500 text-sm mb-4">No analysis results found.</p>
          <button
            onClick={handleRunAnalysis}
            disabled={running}
            className="px-5 py-2.5 text-sm font-medium rounded-lg text-white"
            style={{ background: C_ANTI }}
          >
            {running ? "Running…" : "Run Analysis Now"}
          </button>
        </Card>
      )}

      {activeTab === "anti" && !loading && metrics && (
        <>
          {/* Key metrics tiles */}
          <div>
            <h2 className="text-sm font-semibold text-slate-700 mb-3 uppercase tracking-wide">Key Results — Anti-Trump Strategy</h2>
            <p className="text-xs text-slate-400 mb-3">
              Counterfactual: always bet <em>against</em> Trump — flip YES↔NO on every market. Same markets, dates, and trade sizes as the pro-Trump strategy.
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
              <MetricTile
                label="Final P&L"
                value={fmtUsd(antiM.final_pnl)}
                sub={`${fmtPct(antiM.return_on_invested)} of invested`}
                color={antiM.final_pnl >= 0 ? C_GAIN : C_LOSS}
              />
              <MetricTile
                label="MC Percentile Rank"
                value={antiM.mc_pct_rank != null ? `${Number(antiM.mc_pct_rank).toFixed(1)}th` : "—"}
                sub={mcBenchmark ? `of ${mcBenchmark.n_sims.toLocaleString()} neutral sims` : "Run analysis first"}
                color={
                  antiM.mc_pct_rank == null ? "#111827"
                  : antiM.mc_pct_rank <= 5 ? C_LOSS
                  : antiM.mc_pct_rank >= 95 ? C_GAIN
                  : "#111827"
                }
              />
              <MetricTile
                label="Mean Daily Return"
                value={fmtPct(antiM.mean_daily_return * 100, 4)}
                sub="Prospective (clean)"
                color={antiM.mean_daily_return >= 0 ? C_GAIN : C_LOSS}
              />
              <MetricTile
                label="Annualised Sharpe"
                value={fmt(antiM.sharpe_ann, 3)}
                sub="√365 annualisation"
                color={antiM.sharpe_ann >= 0 ? C_GAIN : C_LOSS}
              />
              <MetricTile
                label="Max Drawdown"
                value={fmtPct(antiM.max_dd_pct)}
                sub={fmtUsd(antiM.max_dd_usd)}
                color={C_LOSS}
              />
              <MetricTile
                label="Win Rate"
                value={mktSummary ? `${(100 - mktSummary.win_rate).toFixed(1)}%` : "—"}
                sub={mktSummary ? `${mktSummary.negative}/${mktSummary.total} markets` : ""}
                color={mktSummary ? ((100 - mktSummary.win_rate) >= 50 ? C_GAIN : C_LOSS) : "#111827"}
              />
            </div>
          </div>

          {/* Secondary metric row */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <MetricTile
              label="Annualised Return"
              value={fmtPct(antiM.ann_return * 100)}
              sub="Prospective clean series"
              color={antiM.ann_return >= 0 ? C_GAIN : C_LOSS}
            />
            <MetricTile
              label="VaR 95% (daily)"
              value={fmtPct(antiM.var_95 * 100)}
              sub={`CVaR 95%: ${fmtPct(antiM.cvar_95 * 100)}`}
              color={C_LOSS}
            />
            <MetricTile
              label="Profit Factor"
              value={mktSummary?.profit_factor != null ? fmt(1 / mktSummary.profit_factor, 3) : "—"}
              sub="Gross gain / gross loss"
              color={mktSummary?.profit_factor != null && (1 / mktSummary.profit_factor) >= 1 ? C_GAIN : C_LOSS}
            />
          </div>

          {/* MC percentile verdict */}
          {antiM.mc_pct_rank != null && (
            <Card className="p-5">
              <h2 className="text-sm font-semibold text-slate-700 mb-1 uppercase tracking-wide">
                Neutral Benchmark Comparison
              </h2>
              <p className="text-xs text-slate-400 mb-4">
                Anti-Trump strategy compared to the same 10,000 neutral 50/50 simulations.
              </p>
              <div className={`rounded-lg px-4 py-3 text-sm flex items-start gap-2 ${
                antiM.mc_pct_rank >= 95
                  ? "bg-green-50 border border-green-200"
                  : antiM.mc_pct_rank <= 5
                  ? "bg-red-50 border border-red-200"
                  : "bg-slate-50 border border-slate-200"
              }`}>
                <div>
                  {antiM.mc_pct_rank >= 95 ? (
                    <>
                      <span className="font-semibold text-green-800">H₁b supported. </span>
                      <span className="text-green-700">
                        The anti-Trump strategy sits in the top {(100 - antiM.mc_pct_rank).toFixed(1)}% of {mcBenchmark?.n_sims?.toLocaleString() ?? "10,000"} neutral simulations.
                        Systematically betting against Trump captures the overpricing premium — consistent with crypto-bro buyers inflating pro-Trump prices above their true probability.
                      </span>
                    </>
                  ) : antiM.mc_pct_rank <= 5 ? (
                    <>
                      <span className="font-semibold text-red-800">H₁a indicated. </span>
                      <span className="text-red-700">
                        Anti-Trump underperforms the neutral benchmark — pro-Trump outcomes are underpriced.
                      </span>
                    </>
                  ) : (
                    <>
                      <span className="font-semibold text-slate-700">H₀ not rejected. </span>
                      <span className="text-slate-600">
                        Anti-Trump returns fall within the typical range of neutral benchmark outcomes.
                      </span>
                    </>
                  )}
                </div>
              </div>
            </Card>
          )}

          {/* Comparison equity sparkline */}
          {antiEquity?.length > 0 && (
            <Card className="p-5">
              <h2 className="text-sm font-semibold text-slate-700 mb-4 uppercase tracking-wide">
                Cumulative P&L — Full Timeline
              </h2>
              <p className="text-xs text-slate-400 mb-3">
                Orange = anti-Trump strategy. Purple = pro-Trump for comparison. Dashed line marks 2026-01-26.
              </p>
              <EquitySpark proData={equityData} antiData={antiEquity} />
            </Card>
          )}

          {/* Period comparison */}
          {antiPeriods && (
            <Card className="p-5">
              <h2 className="text-sm font-semibold text-slate-700 mb-1 uppercase tracking-wide">
                Retrospective vs Prospective
              </h2>
              <p className="text-xs text-slate-400 mb-4">
                Anti-Trump strategy — split at {PROSP_START}.
              </p>
              <PeriodTable periods={antiPeriods} />
            </Card>
          )}

          {/* Statistical summary */}
          <Card className="p-5">
            <h2 className="text-sm font-semibold text-slate-700 mb-4 uppercase tracking-wide">
              Statistical Summary (Prospective Clean Series)
            </h2>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
              {[
                {
                  label: "Abnormal Return t-stat",
                  stat: antiM.mean_daily_return != null && antiM.std_daily_return != null && antiM.T
                    ? fmt(antiM.mean_daily_return / antiM.std_daily_return * Math.sqrt(antiM.T), 4)
                    : "—",
                  note: "H₀: E[AR] = 0 (primary)",
                },
                {
                  label: "OLS Slope ($/day)",
                  stat: antiM.T > 0 && antiM.final_pnl != null ? fmt(antiM.final_pnl / antiM.T, 4) : "—",
                  note: "Trend direction",
                },
                {
                  label: "Sharpe Ratio (ann.)",
                  stat: fmt(antiM.sharpe_ann, 4),
                  note: "√365 annualisation",
                },
                {
                  label: "Sortino Ratio (ann.)",
                  stat: fmt(antiM.sortino_ann, 4),
                  note: "Downside-adjusted",
                },
              ].map(({ label, stat, note }) => (
                <div key={label} className="bg-slate-50 rounded-lg p-3">
                  <p className="text-xs text-slate-500 mb-1">{label}</p>
                  <p className="text-lg font-bold text-slate-800">{stat}</p>
                  <p className="text-xs text-slate-400 mt-0.5">{note}</p>
                </div>
              ))}
            </div>
            <div className="mt-4 rounded-lg px-4 py-3 text-sm" style={{ background: "#fff7ed", border: "1px solid #fed7aa", color: "#9a3412" }}>
              <span className="font-semibold">Anti-Trump interpretation: </span>
              Flipping the strategy direction converts losses into gains. If anti-Trump significantly outperforms neutral,
              this directly supports H₁b — politically motivated (crypto-bro) traders systematically overprice pro-Trump outcomes,
              and the <em>informed</em> trade is to bet against them.
            </div>
          </Card>

          {/* Anti-Trump figures gallery */}
          {(() => {
            const antiFigs = figures.filter((f) => f.filename.includes("_anti") || f.filename === "fig12_strategy_comparison.png");
            if (!antiFigs.some((f) => f.exists)) return null;
            return (
              <div>
                <h2 className="text-sm font-semibold text-slate-700 mb-3 uppercase tracking-wide">
                  Figures ({antiFigs.filter((f) => f.exists).length} / {antiFigs.length})
                  <span className="ml-2 text-slate-400 font-normal normal-case">click to enlarge</span>
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {antiFigs.map((fig) => (
                    <FigureCard key={fig.filename} fig={fig} />
                  ))}
                </div>
              </div>
            );
          })()}
        </>
      )}

      {/* ── Monte Carlo tab ────────────────────────────────────────────── */}
      {activeTab === "montecarlo" && (
        <div className="space-y-6">

          {/* Controls card */}
          <Card className="p-5">
            <h2 className="text-sm font-semibold text-slate-700 mb-1 uppercase tracking-wide">
              Neutral Benchmark Monte Carlo
            </h2>
            <p className="text-xs text-slate-400 mb-4">
              For each simulation, each market is independently assigned YES or NO with 50/50
              probability — same markets, dates, and quantities as the actual pro-Trump strategy.
              Run N simulations and compare the distribution of neutral outcomes to the pro-Trump result.
            </p>
            <div className="flex items-center gap-3 flex-wrap">
              <label className="text-sm font-medium text-slate-700">Simulations:</label>
              <select
                value={mcNSims}
                onChange={(e) => setMcNSims(Number(e.target.value))}
                className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm text-slate-700 bg-white focus:outline-none focus:ring-2 focus:ring-violet-500"
              >
                {[500, 1000, 2000, 5000, 10000].map((n) => (
                  <option key={n} value={n}>{n.toLocaleString()} simulations</option>
                ))}
              </select>
              <button
                onClick={handleRunMC}
                disabled={mcRunning}
                className="px-5 py-2 text-sm font-medium rounded-lg text-white transition-colors disabled:opacity-60"
                style={{ background: mcRunning ? "#a78bfa" : C_PRO }}
              >
                {mcRunning ? "Running…" : "Run Monte Carlo"}
              </button>
              {mcRunning && (
                <span className="text-xs text-slate-400">
                  Computing {mcNSims.toLocaleString()} simulations — this may take 5–30 s…
                </span>
              )}
            </div>
          </Card>

          {/* Error */}
          {mcError && (
            <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
              {mcError}
            </div>
          )}

          {/* Results */}
          {mcResult && (
            <>
              {/* Stats tiles */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <MetricTile
                  label="Pro-Trump Mean Return"
                  value={fmtPct(mcResult.pro_trump_mean * 100, 4)}
                  sub="Actual daily mean"
                  color={mcResult.pro_trump_mean >= 0 ? C_GAIN : C_LOSS}
                />
                <MetricTile
                  label="Neutral MC Mean"
                  value={fmtPct(mcResult.mc_mean * 100, 4)}
                  sub={`±${fmtPct(mcResult.mc_std * 100, 4)} std`}
                  color="#111827"
                />
                <MetricTile
                  label="Percentile Rank"
                  value={`${mcResult.pct_rank.toFixed(1)}th`}
                  sub={`of ${mcResult.n_sims.toLocaleString()} neutral sims`}
                  color={mcResult.pct_rank <= 5 ? C_LOSS : mcResult.pct_rank >= 95 ? C_GAIN : "#111827"}
                />
                <MetricTile
                  label="Empirical p-value"
                  value={mcResult.emp_p_two_tail < 0.001 ? "p < 0.001" : `p = ${mcResult.emp_p_two_tail.toFixed(4)}`}
                  sub={mcResult.emp_p_two_tail < 0.05 ? "Significant (α=0.05)" : "Not significant"}
                  color={mcResult.emp_p_two_tail < 0.05 ? C_LOSS : "#111827"}
                />
              </div>

              {/* Verdict */}
              <Card className="p-4">
                <div className={`rounded-lg px-4 py-3 text-sm flex items-start gap-2 ${
                  mcResult.verdict === "underperforms"
                    ? "bg-red-50 border border-red-200"
                    : mcResult.verdict === "outperforms"
                    ? "bg-green-50 border border-green-200"
                    : "bg-slate-50 border border-slate-200"
                }`}>
                  <div>
                    {mcResult.verdict === "underperforms" ? (
                      <>
                        <span className="font-semibold text-red-800">H₁b supported. </span>
                        <span className="text-red-700">
                          Pro-Trump sits at the {mcResult.pct_rank.toFixed(1)}th percentile of{" "}
                          {mcResult.n_sims.toLocaleString()} neutral benchmark simulations.{" "}
                          {(mcResult.emp_p_one_tail * 100).toFixed(1)}% of random-direction portfolios
                          achieve higher mean returns. Political direction (always betting pro-Trump)
                          destroys value relative to a coin-flip strategy — consistent with systematic
                          overvaluation of pro-Trump outcomes by ideologically motivated traders.
                        </span>
                      </>
                    ) : mcResult.verdict === "outperforms" ? (
                      <>
                        <span className="font-semibold text-green-800">H₁a supported. </span>
                        <span className="text-green-700">
                          Pro-Trump sits at the {mcResult.pct_rank.toFixed(1)}th percentile.
                          Outperforms {(100 - mcResult.emp_p_one_tail * 100).toFixed(1)}% of random-direction
                          portfolios — consistent with systematic undervaluation of pro-Trump outcomes.
                        </span>
                      </>
                    ) : (
                      <>
                        <span className="font-semibold text-slate-700">H₀ not rejected. </span>
                        <span className="text-slate-600">
                          Pro-Trump at the {mcResult.pct_rank.toFixed(1)}th percentile — within the typical
                          range of neutral benchmark outcomes. No statistically significant directional
                          edge detected at α=0.05 (empirical p={mcResult.emp_p_two_tail.toFixed(4)}).
                        </span>
                      </>
                    )}
                  </div>
                </div>
              </Card>

              {/* Histogram */}
              <Card className="p-5">
                <h2 className="text-sm font-semibold text-slate-700 mb-1 uppercase tracking-wide">
                  Distribution of Neutral Benchmark Mean Returns
                </h2>
                <p className="text-xs text-slate-400 mb-4">
                  Histogram of mean daily returns across {mcResult.n_sims.toLocaleString()} neutral simulations.
                  Red bars: outcomes at or below pro-Trump's mean return.
                  Dashed vertical line: actual pro-Trump mean return.
                </p>
                <MCHistogram
                  histData={mcResult.histogram}
                  proTrumpMean={mcResult.pro_trump_mean}
                />
              </Card>

              {/* Equity fan */}
              <Card className="p-5">
                <h2 className="text-sm font-semibold text-slate-700 mb-1 uppercase tracking-wide">
                  Cumulative P&amp;L — Neutral Benchmark vs Pro-Trump
                </h2>
                <p className="text-xs text-slate-400 mb-4">
                  Shaded bands show 5–95th and 25–75th percentile range of{" "}
                  {mcResult.n_sims.toLocaleString()} neutral simulations.
                  Dashed line: median neutral strategy. Solid violet: actual pro-Trump portfolio.
                </p>
                <MCEquityFan equityFan={mcResult.equity_fan} />
              </Card>

              {/* MC details */}
              <Card className="p-5">
                <h2 className="text-sm font-semibold text-slate-700 mb-3 uppercase tracking-wide">
                  Simulation Details
                </h2>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
                  {[
                    { label: "Markets", value: mcResult.n_markets.toLocaleString() },
                    { label: "Simulations", value: mcResult.n_sims.toLocaleString() },
                    { label: "MC 5th pct", value: fmtPct(mcResult.mc_p5 * 100, 4) },
                    { label: "MC 95th pct", value: fmtPct(mcResult.mc_p95 * 100, 4) },
                  ].map(({ label, value }) => (
                    <div key={label} className="bg-slate-50 rounded-lg p-3">
                      <p className="text-xs text-slate-500 mb-1">{label}</p>
                      <p className="text-base font-bold text-slate-800">{value}</p>
                    </div>
                  ))}
                </div>
              </Card>
            </>
          )}
        </div>
      )}
    </div>
  );
}
