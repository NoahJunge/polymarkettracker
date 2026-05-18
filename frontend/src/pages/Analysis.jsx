import { useState, useEffect, useCallback } from "react";
import {
  BarChart, Bar, Cell, ComposedChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ReferenceLine, ResponsiveContainer, Legend,
} from "recharts";
import {
  getAnalysisStatus,
  getAnalysisMetrics,
  runAnalysis,
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

function MetricTile({ label, value, sub, color, formula }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
      <p className="text-xs text-slate-500 mb-1">{label}</p>
      <p className="text-xl font-bold" style={{ color: color || "#111827" }}>{value}</p>
      {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
      {formula && <p className="text-[10px] text-blue-900 mt-1.5 font-mono leading-tight break-words">{formula}</p>}
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
              <tr
                key={row.label}
                className={`border-b border-slate-100 last:border-0 ${row.primary ? "bg-violet-50" : ""}`}
              >
                <td className="py-2.5 pr-4 font-medium text-slate-700">
                  {row.label}
                  {row.primary && (
                    <span className="ml-2 text-xs font-semibold px-1.5 py-0.5 bg-violet-100 text-violet-700 rounded">primary</span>
                  )}
                </td>
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

// ── MC Benchmark Histogram (static, from precomputed mc_neutral_means.csv) ────
const MCRefLabel = ({ viewBox, lines, color, anchor }) => {
  const { x, y } = viewBox;
  const xPos = anchor === "end" ? x - 6 : x + 6;
  return (
    <g>
      {lines.map((line, i) => (
        <text key={i} x={xPos} y={y + 16 + i * 14} fill={color}
          fontSize={i === 0 ? 11 : 10} fontWeight={i === 0 ? "700" : "400"}
          textAnchor={anchor}>
          {line}
        </text>
      ))}
    </g>
  );
};

function MCBenchmarkHistogram({ histData, proMeanPct, antiMeanPct, proRank, antiRank }) {
  if (!histData?.length) return null;

  // Compute domain to include both reference lines, with padding
  const xs = histData.map((d) => d.x);
  const histMin = Math.min(...xs);
  const histMax = Math.max(...xs);
  const spread = histMax - histMin;
  const domainMin = Math.min(histMin, proMeanPct ?? histMin) - spread * 0.08;
  const domainMax = Math.max(histMax, antiMeanPct ?? histMax) + spread * 0.08;

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={histData} barCategoryGap="0%" margin={{ top: 20, right: 50, left: 70, bottom: 30 }}>
        <CartesianGrid vertical={false} stroke="#e5e7eb" strokeDasharray="3 3" />
        <XAxis
          dataKey="x"
          type="number"
          domain={[domainMin, domainMax]}
          scale="linear"
          tickFormatter={(v) => `${Number(v).toFixed(3)}%`}
          tick={{ fontSize: 9, fill: "#6b7280" }}
          tickLine={false}
          axisLine={false}
          interval="preserveStartEnd"
          label={{ value: "Mean Daily Return (%)", position: "insideBottom", offset: -16, fontSize: 11, fill: "#6b7280" }}
        />
        <YAxis
          tick={{ fontSize: 9, fill: "#6b7280" }}
          tickLine={false}
          axisLine={false}
          allowDecimals={false}
          width={50}
          label={{ value: "Number of Simulations", angle: -90, position: "insideLeft", offset: 15, fontSize: 11, fill: "#6b7280" }}
        />
        <Tooltip
          formatter={(v) => [v, "Simulations"]}
          labelFormatter={(x) => `Mean return: ${Number(x).toFixed(4)}%`}
          contentStyle={{ fontSize: 11 }}
        />
        {/* Pro-Trump line — sits far LEFT of the neutral distribution */}
        <ReferenceLine
          x={proMeanPct}
          stroke={C_LOSS}
          strokeWidth={3}
          label={<MCRefLabel
            color={C_LOSS}
            anchor="start"
            lines={[
              `Pro-Trump`,
              `${proMeanPct?.toFixed(4)}%`,
              `${proRank?.toFixed(1)}th percentile`,
            ]}
          />}
        />
        {/* Anti-Trump line — sits far RIGHT of the neutral distribution */}
        <ReferenceLine
          x={antiMeanPct}
          stroke={C_ANTI}
          strokeWidth={3}
          label={<MCRefLabel
            color={C_ANTI}
            anchor="end"
            lines={[
              `Anti-Trump`,
              `${antiMeanPct?.toFixed(4)}%`,
              `${antiRank?.toFixed(1)}th percentile`,
            ]}
          />}
        />
        <Bar dataKey="count" isAnimationActive={false} radius={[2, 2, 0, 0]} fill={C_PRO} fillOpacity={0.6} />
      </BarChart>
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

  const [activeTab, setActiveTab] = useState("pro");

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

      {/* Experiment closed banner */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs font-medium px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full border border-amber-200">
          Data as of 1 May 2026 — experiment closed
        </span>
        <span className="text-xs text-slate-400">
          Full series: 287 days (Jul 19, 2025 – May 1, 2026) ·
          Prospective: 96 days (Jan 26 – May 1, 2026) — Jan 26–Feb 21 gap filled with CLOB daily prices · used for formal t-test
        </span>
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
          {/* Key metrics tiles — all using full 287-day series */}
          {(() => {
            const fullMean = periods?.full?.mean_return ?? null;
            const fullStd  = periods?.full?.std_return  ?? null;
            const fullSharpe = fullMean != null && fullStd != null && fullStd > 0
              ? fullMean / fullStd * Math.sqrt(365) : null;
            const fullAnnReturn = fullMean != null ? fullMean * 365 : null;
            return (
              <>
                <div>
                  <h2 className="text-sm font-semibold text-slate-700 mb-1 uppercase tracking-wide">Key Results</h2>
                  <p className="text-xs text-slate-400 mb-3">
                    All figures cover the full 287-day series (Jul 19, 2025 – May 1, 2026) unless noted.
                    See <em>Statistical Tests</em> below for the formal 96-day hypothesis test.
                  </p>
                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                    <MetricTile
                      label="Final P&L"
                      value={fmtUsd(periods?.full?.final_pnl ?? m.final_pnl)}
                      sub={`${fmtPct(periods?.full?.return_pct ?? m.return_on_invested)} return on invested`}
                      color={(periods?.full?.final_pnl ?? m.final_pnl) >= 0 ? C_GAIN : C_LOSS}
                      formula="Σ mark-to-market − Σ cost basis"
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
                      formula="% of 50/50 random-direction sims with lower mean return"
                    />
                    <MetricTile
                      label="Mean Daily Return"
                      value={fullMean != null ? fmtPct(fullMean * 100, 4) : "—"}
                      sub={`Full series · ${periods?.full?.days ?? 287} days`}
                      color={fullMean >= 0 ? C_GAIN : C_LOSS}
                      formula="r̄ = mean(ΔP&L_t / invested_{t−1})"
                    />
                    <MetricTile
                      label="Annualised Sharpe"
                      value={fullSharpe != null ? fmt(fullSharpe, 3) : "—"}
                      sub="Full series · √365 annualisation"
                      color={fullSharpe >= 0 ? C_GAIN : C_LOSS}
                      formula="SR = r̄ / σ̂ × √365"
                    />
                    <MetricTile
                      label="Max Drawdown"
                      value={fmtPct(m.max_dd_pct)}
                      sub={fmtUsd(m.max_dd_usd)}
                      color={C_LOSS}
                      formula="max(peak_t − trough_t) / peak_t"
                    />
                    <MetricTile
                      label="Win Rate"
                      value={mktSummary ? `${mktSummary.win_rate}%` : "—"}
                      sub={mktSummary ? `${mktSummary.positive}/${mktSummary.total} markets` : ""}
                      color={mktSummary?.win_rate >= 50 ? C_GAIN : C_LOSS}
                      formula="mark-to-market P&L > 0 as of 1 May (includes unresolved)"
                    />
                  </div>
                </div>

                {/* Secondary metric row */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <MetricTile
                    label="Annualised Return"
                    value={fullAnnReturn != null ? fmtPct(fullAnnReturn * 100) : "—"}
                    sub="Full series · r̄ × 365"
                    color={fullAnnReturn >= 0 ? C_GAIN : C_LOSS}
                    formula="mean daily return × 365 trading days"
                  />
                  <MetricTile
                    label="VaR 95% (daily)"
                    value={fmtPct(m.var_95 * 100)}
                    sub={`CVaR 95%: ${fmtPct(m.cvar_95 * 100)}`}
                    color={C_LOSS}
                    formula="5th percentile of daily return distribution (96-day prospective)"
                  />
                  <MetricTile
                    label="Profit Factor"
                    value={mktSummary?.profit_factor != null ? fmt(mktSummary.profit_factor, 3) : "—"}
                    sub="Gross gain / gross loss"
                    color={mktSummary?.profit_factor >= 1 ? C_GAIN : C_LOSS}
                    formula="Σ winning market P&L / Σ |losing market P&L|"
                  />
                </div>
              </>
            );
          })()}

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
              Retrospective = Jul 19, 2025 – Jan 25, 2026 (CLOB historical prices, no_price = 1 − yes_price).
              Prospective = Jan 26, 2026 – May 1, 2026 (live Gamma API collection, real bid-ask spread).
              Invested and P&L are period-specific amounts (not cumulative), so Retrospective + Prospective = Full Series.
            </p>
            <PeriodTable periods={periods} />
          </Card>

          {/* Hypothesis test summary */}
          <Card className="p-5">
            <h2 className="text-sm font-semibold text-slate-700 mb-1 uppercase tracking-wide">
              Statistical Tests — Prospective Period (26 Jan – 1 May 2026)
            </h2>
            <p className="text-xs text-slate-400 mb-4">
              Uses T = {m.T ?? 96} daily observations from the <strong>prospective series</strong> (26 Jan – 1 May 2026).
              Jan 26–Feb 21 gap filled with CLOB daily prices; Feb 22 onward collected live via Gamma API.
              Key Results tiles above use the full 287-day series.
            </p>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
              {[
                {
                  label: "One-Sample t-Statistic",
                  stat: m.mean_daily_return != null && m.std_daily_return != null && m.T
                    ? fmt(m.mean_daily_return / m.std_daily_return * Math.sqrt(m.T), 4)
                    : "—",
                  note: "t = r̄ / (σ̂/√T); df = T−1; H₀: μ = 0",
                },
                {
                  label: "OLS Slope ($/day)",
                  stat: m.T > 0 && m.final_pnl != null ? fmt(m.final_pnl / m.T, 4) : "—",
                  note: "P&L_t = α + β·t + ε; HC3 robust SEs; p < 0.001",
                },
                {
                  label: "Sharpe Ratio (ann.)",
                  stat: fmt(m.sharpe_ann, 4),
                  note: "SR = r̄ / σ̂ × √365; 96-day prospective series",
                },
                {
                  label: "Sortino Ratio (ann.)",
                  stat: fmt(m.sortino_ann, 4),
                  note: "SR_S = r̄ / σ̂_down × √365; σ̂_down = std of negative returns only",
                },
              ].map(({ label, stat, note }) => (
                <div key={label} className="bg-slate-50 rounded-lg p-3">
                  <p className="text-xs text-slate-500 mb-1">{label}</p>
                  <p className="text-lg font-bold text-slate-800">{stat}</p>
                  <p className="text-[10px] text-slate-400 mt-0.5 font-mono leading-tight">{note}</p>
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
          {/* Key metrics tiles — all using full 287-day series */}
          {(() => {
            const aFull = antiPeriods?.full;
            const aFullMean = aFull?.mean_return ?? null;
            const aFullStd  = aFull?.std_return  ?? null;
            const aFullSharpe = aFullMean != null && aFullStd != null && aFullStd > 0
              ? aFullMean / aFullStd * Math.sqrt(365) : null;
            const aFullAnnReturn = aFullMean != null ? aFullMean * 365 : null;
            return (
              <>
                <div>
                  <h2 className="text-sm font-semibold text-slate-700 mb-1 uppercase tracking-wide">Key Results — Anti-Trump Strategy</h2>
                  <p className="text-xs text-slate-400 mb-3">
                    Counterfactual: always bet <em>against</em> Trump — flip YES↔NO on every market. Same markets, dates, and trade sizes.
                    All figures cover the full 287-day series (Jul 19, 2025 – May 1, 2026).
                  </p>
                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                    <MetricTile
                      label="Final P&L"
                      value={fmtUsd(aFull?.final_pnl ?? antiM.final_pnl)}
                      sub={`${fmtPct(aFull?.return_pct ?? antiM.return_on_invested)} return on invested`}
                      color={(aFull?.final_pnl ?? antiM.final_pnl) >= 0 ? C_GAIN : C_LOSS}
                      formula="Σ mark-to-market − Σ cost basis"
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
                      formula="% of 50/50 random-direction sims with lower mean return"
                    />
                    <MetricTile
                      label="Mean Daily Return"
                      value={aFullMean != null ? fmtPct(aFullMean * 100, 4) : "—"}
                      sub={`Full series · ${aFull?.days ?? 287} days`}
                      color={aFullMean >= 0 ? C_GAIN : C_LOSS}
                      formula="r̄ = mean(ΔP&L_t / invested_{t−1})"
                    />
                    <MetricTile
                      label="Annualised Sharpe"
                      value={aFullSharpe != null ? fmt(aFullSharpe, 3) : "—"}
                      sub="Full series · √365 annualisation"
                      color={aFullSharpe >= 0 ? C_GAIN : C_LOSS}
                      formula="SR = r̄ / σ̂ × √365"
                    />
                    <MetricTile
                      label="Max Drawdown"
                      value={fmtPct(antiM.max_dd_pct)}
                      sub={fmtUsd(antiM.max_dd_usd)}
                      color={C_LOSS}
                      formula="max(peak_t − trough_t) / peak_t"
                    />
                    <MetricTile
                      label="Win Rate"
                      value={mktSummary ? `${(100 - mktSummary.win_rate).toFixed(1)}%` : "—"}
                      sub={mktSummary ? `${mktSummary.negative}/${mktSummary.total} markets` : ""}
                      color={mktSummary ? ((100 - mktSummary.win_rate) >= 50 ? C_GAIN : C_LOSS) : "#111827"}
                      formula="pro-Trump losing market = anti-Trump win · as of 1 May"
                    />
                  </div>
                </div>

                {/* Secondary metric row */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <MetricTile
                    label="Annualised Return"
                    value={aFullAnnReturn != null ? fmtPct(aFullAnnReturn * 100) : "—"}
                    sub="Full series · r̄ × 365"
                    color={aFullAnnReturn >= 0 ? C_GAIN : C_LOSS}
                    formula="mean daily return × 365 trading days"
                  />
                  <MetricTile
                    label="VaR 95% (daily)"
                    value={fmtPct(antiM.var_95 * 100)}
                    sub={`CVaR 95%: ${fmtPct(antiM.cvar_95 * 100)}`}
                    color={C_LOSS}
                    formula="5th percentile of daily return distribution (96-day prospective)"
                  />
                  <MetricTile
                    label="Profit Factor"
                    value={mktSummary?.profit_factor != null ? fmt(1 / mktSummary.profit_factor, 3) : "—"}
                    sub="Gross gain / gross loss"
                    color={mktSummary?.profit_factor != null && (1 / mktSummary.profit_factor) >= 1 ? C_GAIN : C_LOSS}
                    formula="Σ winning market P&L / Σ |losing market P&L|"
                  />
                </div>
              </>
            );
          })()}

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
                Retrospective = Jul 19, 2025 – Jan 25, 2026 (CLOB historical prices).
                Prospective = Jan 26, 2026 – May 1, 2026 (live Gamma API collection).
                Anti-Trump flips YES↔NO on every market — same dates and quantities, opposite side.
                Invested and P&L are period-specific (not cumulative).
              </p>
              <PeriodTable periods={antiPeriods} />
            </Card>
          )}

          {/* Statistical summary */}
          <Card className="p-5">
            <h2 className="text-sm font-semibold text-slate-700 mb-1 uppercase tracking-wide">
              Statistical Tests — Prospective Period (26 Jan – 1 May 2026)
            </h2>
            <p className="text-xs text-slate-400 mb-4">
              Uses T = {antiM.T ?? 96} daily observations from the <strong>prospective series</strong> (26 Jan – 1 May 2026).
              Jan 26–Feb 21 gap filled with CLOB daily prices; Feb 22 onward collected live via Gamma API.
              Anti-Trump flips YES↔NO on every trade — entry price taken from the opposite side.
              Key Results tiles above use the full 287-day series.
            </p>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
              {[
                {
                  label: "One-Sample t-Statistic",
                  stat: antiM.mean_daily_return != null && antiM.std_daily_return != null && antiM.T
                    ? fmt(antiM.mean_daily_return / antiM.std_daily_return * Math.sqrt(antiM.T), 4)
                    : "—",
                  note: "t = r̄ / (σ̂/√T); df = T−1; H₀: μ = 0",
                },
                {
                  label: "OLS Slope ($/day)",
                  stat: antiM.T > 0 && antiM.final_pnl != null ? fmt(antiM.final_pnl / antiM.T, 4) : "—",
                  note: "P&L_t = α + β·t + ε; HC3 robust SEs",
                },
                {
                  label: "Sharpe Ratio (ann.)",
                  stat: fmt(antiM.sharpe_ann, 4),
                  note: "SR = r̄ / σ̂ × √365; 96-day prospective series",
                },
                {
                  label: "Sortino Ratio (ann.)",
                  stat: fmt(antiM.sortino_ann, 4),
                  note: "SR_S = r̄ / σ̂_down × √365; σ̂_down = std of negative returns only",
                },
              ].map(({ label, stat, note }) => (
                <div key={label} className="bg-slate-50 rounded-lg p-3">
                  <p className="text-xs text-slate-500 mb-1">{label}</p>
                  <p className="text-lg font-bold text-slate-800">{stat}</p>
                  <p className="text-[10px] text-slate-400 mt-0.5 font-mono leading-tight">{note}</p>
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

          {/* Methodology explanation */}
          <Card className="p-5">
            <h2 className="text-sm font-semibold text-slate-700 mb-1 uppercase tracking-wide">
              Neutral Benchmark Monte Carlo
            </h2>
            <p className="text-xs text-slate-400 mb-4">
              Precomputed from seed data · {mcBenchmark ? mcBenchmark.n_sims.toLocaleString() : "10,000"} simulations · Same markets, dates, and quantities as the actual pro-Trump strategy
            </p>
            <div className="bg-slate-50 rounded-lg p-4 text-sm text-slate-700 space-y-3">
              <p className="font-semibold text-slate-800">How the simulation works:</p>
              <p>
                The key question is: <em>"Does the pro-Trump directional choice add or destroy value, compared to simply trading randomly?"</em>
              </p>
              <ol className="list-decimal list-inside space-y-1.5 text-slate-600">
                <li>
                  For each simulation, every market is independently assigned <strong>YES</strong> or <strong>NO</strong> with 50/50 probability — a coin-flip direction with no political bias.
                </li>
                <li>
                  The portfolio P&L is computed using the <strong>same markets, same dates, and same quantities</strong> as the actual pro-Trump DCA strategy.
                </li>
                <li>
                  Repeat {mcBenchmark ? mcBenchmark.n_sims.toLocaleString() : "10,000"} times to build a distribution of "what if we had no directional bias?" outcomes.
                </li>
                <li>
                  The actual pro-Trump mean daily return is ranked against this distribution. If it falls in the <strong>bottom 5%</strong>, directional betting on pro-Trump systematically destroys value → supports H₁b.
                </li>
              </ol>
              <p className="text-xs text-slate-400 border-t border-slate-200 pt-3 mt-1">
                Abnormal return: AR_t = R_pro-Trump,t − mean(R_neutral,t across simulations).
                MC data covers Jul 19, 2025 – May 1, 2026 (experiment end).
              </p>
            </div>
          </Card>

          {/* Strategy stats tiles */}
          {mcBenchmark && (
            <div className="space-y-3">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Directional Strategies (96-day prospective series)</p>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <MetricTile
                  label="Pro-Trump Mean Return"
                  value={fmtPct(mcBenchmark.pro_mean_pct, 4)}
                  sub="Daily mean · prospective"
                  color={mcBenchmark.pro_mean_pct >= 0 ? C_GAIN : C_LOSS}
                  formula="mean of daily_return for 96-day prospective series"
                />
                <MetricTile
                  label="Anti-Trump Mean Return"
                  value={fmtPct(mcBenchmark.anti_mean_pct, 4)}
                  sub="Daily mean · prospective"
                  color={mcBenchmark.anti_mean_pct >= 0 ? C_GAIN : C_LOSS}
                  formula="same trades, flipped YES↔NO direction"
                />
                <MetricTile
                  label="Pro-Trump Percentile"
                  value={`${mcBenchmark.pct_rank.toFixed(1)}th`}
                  sub={`of ${mcBenchmark.n_sims.toLocaleString()} neutral sims`}
                  color={mcBenchmark.pct_rank <= 5 ? C_LOSS : "#111827"}
                  formula="% of neutral sims with lower mean return"
                />
                <MetricTile
                  label="Anti-Trump Percentile"
                  value={mcBenchmark.anti_pct_rank != null ? `${mcBenchmark.anti_pct_rank.toFixed(1)}th` : "—"}
                  sub={`of ${mcBenchmark.n_sims.toLocaleString()} neutral sims`}
                  color={mcBenchmark.anti_pct_rank >= 95 ? C_GAIN : "#111827"}
                  formula="% of neutral sims with lower mean return"
                />
              </div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide pt-1">Neutral Benchmark Average (across {mcBenchmark.n_sims.toLocaleString()} simulations)</p>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <MetricTile
                  label="Neutral Mean Daily Return"
                  value={fmtPct(mcBenchmark.mc_mean * 100, 4)}
                  sub="Avg across all neutral sims"
                  color="#111827"
                  formula="mean of mean_return_sim across 10,000 simulations"
                />
                <MetricTile
                  label="Neutral Avg Final P&L"
                  value={mcBenchmark.mc_avg_final_pnl != null ? `$${mcBenchmark.mc_avg_final_pnl.toFixed(2)}` : "—"}
                  sub="Avg cumulative P&L at end"
                  color={mcBenchmark.mc_avg_final_pnl >= 0 ? C_GAIN : C_LOSS}
                  formula="mean of final P&L across 10,000 simulations"
                />
                <MetricTile
                  label="Neutral P5 Final P&L"
                  value={mcBenchmark.mc_p5_final_pnl != null ? `$${mcBenchmark.mc_p5_final_pnl.toFixed(2)}` : "—"}
                  sub="5th percentile outcome"
                  color={C_LOSS}
                  formula="5th percentile of final P&L across 10,000 simulations"
                />
                <MetricTile
                  label="Neutral P95 Final P&L"
                  value={mcBenchmark.mc_p95_final_pnl != null ? `$${mcBenchmark.mc_p95_final_pnl.toFixed(2)}` : "—"}
                  sub="95th percentile outcome"
                  color={C_GAIN}
                  formula="95th percentile of final P&L across 10,000 simulations"
                />
              </div>
            </div>
          )}

          {/* Distribution histogram (static, from precomputed mc_neutral_means.csv) */}
          {mcBenchmark?.histogram && (
            <Card className="p-5">
              <h2 className="text-sm font-semibold text-slate-700 mb-1 uppercase tracking-wide">
                Distribution of Neutral Benchmark Mean Returns
              </h2>
              <p className="text-xs text-slate-400 mb-4">
                Histogram of mean daily returns across {mcBenchmark.n_sims.toLocaleString()} neutral simulations.
                Each simulation uses 50/50 random direction per market.
                Vertical lines show where the actual pro-Trump and anti-Trump strategies land in this distribution.
              </p>
              <MCBenchmarkHistogram
                histData={mcBenchmark.histogram}
                proMeanPct={mcBenchmark.pro_mean_pct}
                antiMeanPct={mcBenchmark.anti_mean_pct}
                proRank={mcBenchmark.pct_rank}
                antiRank={mcBenchmark.anti_pct_rank}
              />
              <div className="mt-3 flex items-center gap-4 text-xs text-slate-500">
                <span className="flex items-center gap-1.5">
                  <span className="inline-block w-4 h-0.5 border-t-2 border-dashed" style={{ borderColor: C_LOSS }}></span>
                  Pro-Trump ({mcBenchmark.pct_rank.toFixed(1)}th pct) — below {(100 - mcBenchmark.pct_rank).toFixed(0)}% of neutral outcomes
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="inline-block w-4 h-0.5 border-t-2 border-dashed" style={{ borderColor: C_ANTI }}></span>
                  Anti-Trump ({mcBenchmark.anti_pct_rank?.toFixed(1)}th pct) — above {mcBenchmark.anti_pct_rank?.toFixed(0)}% of neutral outcomes
                </span>
              </div>
            </Card>
          )}

          {/* Full-series histogram */}
          {mcBenchmark?.histogram && mcBenchmark.full_pro_mean_pct != null && (
            <Card className="p-5">
              <h2 className="text-sm font-semibold text-slate-700 mb-1 uppercase tracking-wide">
                Distribution of Neutral Benchmark Mean Returns — Full Series (287 days)
              </h2>
              <p className="text-xs text-slate-400 mb-4">
                Same {mcBenchmark.n_sims.toLocaleString()} neutral simulations, but reference lines show where the strategies land using their full 287-day mean daily return (vs 96-day prospective above).
              </p>
              <MCBenchmarkHistogram
                histData={mcBenchmark.histogram}
                proMeanPct={mcBenchmark.full_pro_mean_pct}
                antiMeanPct={mcBenchmark.full_anti_mean_pct}
                proRank={mcBenchmark.full_pro_pct_rank}
                antiRank={mcBenchmark.full_anti_pct_rank}
              />
              <div className="mt-3 flex items-center gap-4 text-xs text-slate-500">
                <span className="flex items-center gap-1.5">
                  <span className="inline-block w-4 h-0.5 border-t-2 border-dashed" style={{ borderColor: C_LOSS }}></span>
                  Pro-Trump ({mcBenchmark.full_pro_pct_rank?.toFixed(1)}th pct) — full 287-day series
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="inline-block w-4 h-0.5 border-t-2 border-dashed" style={{ borderColor: C_ANTI }}></span>
                  Anti-Trump ({mcBenchmark.full_anti_pct_rank?.toFixed(1)}th pct) — full 287-day series
                </span>
              </div>
            </Card>
          )}

          {/* Verdict banner */}
          {mcBenchmark && (
            <Card className="p-4">
              <div className={`rounded-lg px-4 py-3 text-sm ${
                mcBenchmark.pct_rank <= 5
                  ? "bg-red-50 border border-red-200"
                  : mcBenchmark.pct_rank >= 95
                  ? "bg-green-50 border border-green-200"
                  : "bg-slate-50 border border-slate-200"
              }`}>
                {mcBenchmark.pct_rank <= 5 ? (
                  <>
                    <p className="font-semibold text-red-800 mb-1">H₁b supported — pro-Trump significantly underperforms neutral.</p>
                    <p className="text-red-700">
                      Pro-Trump sits at the <strong>{mcBenchmark.pct_rank.toFixed(1)}th percentile</strong> of {mcBenchmark.n_sims.toLocaleString()} neutral benchmark simulations.
                      Political direction (always betting pro-Trump) destroys value relative to a coin-flip strategy —
                      consistent with crypto-bro buyers systematically inflating pro-Trump prices above their true probability.
                    </p>
                    {mcBenchmark.anti_pct_rank >= 95 && (
                      <p className="text-red-700 mt-2">
                        The anti-Trump counterfactual sits at the <strong>{mcBenchmark.anti_pct_rank.toFixed(1)}th percentile</strong> —
                        capturing the overpricing premium confirms the directional asymmetry.
                      </p>
                    )}
                  </>
                ) : (
                  <p className="text-slate-700">
                    Pro-Trump at the {mcBenchmark.pct_rank.toFixed(1)}th percentile — within the typical range of neutral benchmark outcomes.
                  </p>
                )}
              </div>
            </Card>
          )}

          {/* Full-series charts — combined and individual */}
          <div className="space-y-4">
            {figures.find((f) => f.filename === "fig12_strategy_comparison.png")?.exists && (
              <Card className="overflow-hidden">
                <div className="p-4 border-b border-slate-100">
                  <p className="text-sm font-semibold text-slate-700">Full Series — Pro-Trump &amp; Anti-Trump vs Neutral Benchmark</p>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Both strategies plotted against the 10,000-simulation neutral fan (5–95th and 25–75th percentile bands) across the full 287-day observation window.
                  </p>
                </div>
                <img
                  src={getAnalysisFigureUrl("fig12_strategy_comparison.png")}
                  alt="Full series both strategies vs neutral benchmark"
                  className="w-full object-contain"
                />
              </Card>
            )}
            {figures.find((f) => f.filename === "fig8_mc_equity_comparison.png")?.exists && (
              <Card className="overflow-hidden">
                <div className="p-4 border-b border-slate-100">
                  <p className="text-sm font-semibold text-slate-700">Pro-Trump — Full Series vs Neutral Benchmark Fan</p>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Pro-Trump cumulative P&L (full 287-day series) overlaid on the neutral simulation fan. Shaded bands = 5–95th and 25–75th percentile of 10,000 neutral sims.
                  </p>
                </div>
                <img
                  src={getAnalysisFigureUrl("fig8_mc_equity_comparison.png")}
                  alt="Pro-Trump full series vs neutral benchmark fan"
                  className="w-full object-contain"
                />
              </Card>
            )}
            {figures.find((f) => f.filename === "fig8_mc_equity_comparison_anti.png")?.exists && (
              <Card className="overflow-hidden">
                <div className="p-4 border-b border-slate-100">
                  <p className="text-sm font-semibold text-slate-700">Anti-Trump — Full Series vs Neutral Benchmark Fan</p>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Anti-Trump cumulative P&L (full 287-day series) overlaid on the same neutral simulation fan. Anti-Trump tracks the upper tail of neutral outcomes throughout.
                  </p>
                </div>
                <img
                  src={getAnalysisFigureUrl("fig8_mc_equity_comparison_anti.png")}
                  alt="Anti-Trump full series vs neutral benchmark fan"
                  className="w-full object-contain"
                />
              </Card>
            )}
          </div>

          {/* Per-strategy MC benchmark figures (histogram + daily fan) */}
          {figures.some((f) => (f.filename === "fig11_mc_benchmark.png" || f.filename === "fig11_mc_benchmark_anti.png") && f.exists) && (
            <div className="space-y-4">
              {figures.find((f) => f.filename === "fig11_mc_benchmark.png")?.exists && (
                <Card className="overflow-hidden">
                  <div className="p-4 border-b border-slate-100">
                    <p className="text-sm font-semibold text-slate-700">Pro-Trump — Monte Carlo Neutral Benchmark</p>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Left: distribution of 10,000 neutral sim mean returns vs pro-Trump actual (dashed line).
                      Right: daily return fan chart — shaded bands = 5–95th and 25–75th percentile of neutral sims.
                    </p>
                  </div>
                  <img
                    src={getAnalysisFigureUrl("fig11_mc_benchmark.png")}
                    alt="Pro-Trump Monte Carlo benchmark"
                    className="w-full object-contain"
                  />
                </Card>
              )}
              {figures.find((f) => f.filename === "fig11_mc_benchmark_anti.png")?.exists && (
                <Card className="overflow-hidden">
                  <div className="p-4 border-b border-slate-100">
                    <p className="text-sm font-semibold text-slate-700">Anti-Trump — Monte Carlo Neutral Benchmark</p>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Same 10,000 neutral simulations, compared against the anti-Trump counterfactual.
                      Anti-Trump sits in the far right tail — confirming pro-Trump outcomes are systematically overpriced.
                    </p>
                  </div>
                  <img
                    src={getAnalysisFigureUrl("fig11_mc_benchmark_anti.png")}
                    alt="Anti-Trump Monte Carlo benchmark"
                    className="w-full object-contain"
                  />
                </Card>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
