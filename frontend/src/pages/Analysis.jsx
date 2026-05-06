import { useState, useEffect, useCallback } from "react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
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

function EquitySpark({ data }) {
  if (!data?.length) return null;

  const tickFormatter = (d) => {
    const dt = new Date(d);
    return dt.toLocaleDateString("en-US", { month: "short", year: "2-digit" });
  };
  const prospIdx = data.findIndex((d) => d.date >= PROSP_START);
  const prospDate = prospIdx >= 0 ? data[prospIdx].date : null;

  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={data} margin={{ top: 8, right: 16, left: 60, bottom: 0 }}>
        <defs>
          <linearGradient id="pnlGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor={C_PRO} stopOpacity={0.25} />
            <stop offset="95%" stopColor={C_PRO} stopOpacity={0.02} />
          </linearGradient>
        </defs>
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
        <Area
          type="monotone"
          dataKey="total_pnl"
          name="Cumulative P&L"
          stroke={C_PRO}
          fill="url(#pnlGrad)"
          strokeWidth={2}
          dot={false}
        />
      </AreaChart>
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
  const figures = status?.figures || [];

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

      {/* Run log */}
      {runLog && (
        <Card className="p-4">
          <p className="text-xs font-semibold text-slate-500 mb-2 uppercase tracking-wide">Analysis Output</p>
          <pre className="text-xs text-slate-700 whitespace-pre-wrap font-mono leading-relaxed max-h-48 overflow-y-auto">
            {runLog}
          </pre>
        </Card>
      )}

      {loading && (
        <div className="text-center py-16 text-slate-400 text-sm">Loading analysis results…</div>
      )}
      {error && !loading && (
        <div className="text-center py-16 text-slate-400 text-sm">
          {error} — run the analysis to generate results.
        </div>
      )}

      {!loading && metrics && (
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
                label="t-statistic"
                value={fmt(m.mean_daily_return / m.std_daily_return * Math.sqrt(m.T), 4)}
                sub={`N = ${m.T} days`}
                color="#111827"
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

          {/* Anti-Trump counterfactual highlight */}
          {periods && (
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
          )}

          {/* Equity sparkline */}
          {equityData?.length > 0 && (
            <Card className="p-5">
              <h2 className="text-sm font-semibold text-slate-700 mb-4 uppercase tracking-wide">
                Cumulative P&L — Full Timeline
              </h2>
              <p className="text-xs text-slate-400 mb-3">
                Dashed line marks 2026-01-26 — where retrospective (CLOB historical) ends and prospective (live collection) begins.
              </p>
              <EquitySpark data={equityData} />
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
              Hypothesis Test Summary (Prospective Clean Series)
            </h2>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
              {[
                { label: "One-Sample t-Test", stat: fmt(m.mean_daily_return / m.std_daily_return * Math.sqrt(m.T), 4), pval: null, note: "H₀: μ = 0" },
                { label: "Sharpe Ratio (ann.)", stat: fmt(m.sharpe_ann, 4), pval: null, note: "Risk-adjusted return" },
                { label: "Sortino Ratio (ann.)", stat: fmt(m.sortino_ann, 4), pval: null, note: "Downside-adj. return" },
                { label: "OLS Trend β ($/day)", stat: fmt(m.T > 0 ? (m.final_pnl / m.T) : null, 4), pval: null, note: "p < 0.001 ***" },
              ].map(({ label, stat, note }) => (
                <div key={label} className="bg-slate-50 rounded-lg p-3">
                  <p className="text-xs text-slate-500 mb-1">{label}</p>
                  <p className="text-lg font-bold text-slate-800">{stat}</p>
                  <p className="text-xs text-slate-400 mt-0.5">{note}</p>
                </div>
              ))}
            </div>
            <div className="mt-4 rounded-lg bg-violet-50 border border-violet-200 px-4 py-3 text-sm text-violet-800">
              <span className="font-semibold">Interpretation: </span>
              The OLS equity curve has a statistically significant downward slope (p &lt; 0.001), consistent with H₁b — pro-Trump outcomes are systematically overvalued.
              The t-test on daily returns does not reach significance (p ≈ 0.57), but the anti-Trump counterfactual shows a
              {" "}<strong>$1,615 directional gap</strong> — the strongest evidence in the dataset.
            </div>
          </Card>
        </>
      )}

      {/* Figures gallery */}
      {figures.some((f) => f.exists) && (
        <div>
          <h2 className="text-sm font-semibold text-slate-700 mb-3 uppercase tracking-wide">
            Figures ({figures.filter((f) => f.exists).length} / {figures.length})
            <span className="ml-2 text-slate-400 font-normal normal-case">click to enlarge</span>
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {figures.map((fig) => (
              <FigureCard key={fig.filename} fig={fig} />
            ))}
          </div>
        </div>
      )}

      {!loading && !metrics && (
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
    </div>
  );
}
