export default function PortfolioSummary({ summary }) {
  if (!summary) return null;

  const totalPnl = summary.total_unrealized_pnl + summary.total_realized_pnl;
  const pnlPct = summary.total_cost_basis > 0
    ? (totalPnl / summary.total_cost_basis) * 100
    : 0;

  const cards = [
    {
      label: "Portfolio Value",
      value: `$${summary.total_equity.toFixed(2)}`,
      sub: "Mark-to-market",
      color: "text-slate-900",
    },
    {
      label: "Total P&L",
      value: `${totalPnl >= 0 ? "+" : ""}$${totalPnl.toFixed(2)}`,
      sub: `${pnlPct >= 0 ? "+" : ""}${pnlPct.toFixed(2)}% of invested`,
      color: totalPnl >= 0 ? "text-green-600" : "text-red-600",
    },
    {
      label: "Cost Basis",
      value: `$${summary.total_cost_basis.toFixed(2)}`,
      sub: `${summary.total_trades.toLocaleString()} trades`,
      color: "text-slate-900",
    },
    {
      label: "Open Markets",
      value: summary.open_position_count,
      sub: "At experiment close",
      color: "text-slate-900",
    },
  ];

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full border border-amber-200">
          Data as of 1 May 2026 — experiment closed
        </span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {cards.map((c) => (
          <div key={c.label} className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
            <p className="text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">{c.label}</p>
            <p className={`text-2xl font-semibold ${c.color}`}>{c.value}</p>
            {c.sub && <p className="text-xs text-slate-400 mt-1">{c.sub}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}
