export default function PortfolioSummary({ summary }) {
  if (!summary) return null;

  const cards = [
    {
      label: "Total Equity",
      value: `$${summary.total_equity.toFixed(2)}`,
      color: "text-slate-900",
    },
    {
      label: "Unrealized P&L",
      value: `${summary.total_unrealized_pnl >= 0 ? "+" : ""}$${summary.total_unrealized_pnl.toFixed(2)}`,
      color:
        summary.total_unrealized_pnl >= 0 ? "text-green-600" : "text-red-600",
    },
    {
      label: "Realized P&L",
      value: `${summary.total_realized_pnl >= 0 ? "+" : ""}$${summary.total_realized_pnl.toFixed(2)}`,
      color:
        summary.total_realized_pnl >= 0 ? "text-green-600" : "text-red-600",
    },
    {
      label: "Open Positions",
      value: summary.open_position_count,
      color: "text-slate-900",
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {cards.map((c) => (
        <div key={c.label} className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
          <p className="text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">{c.label}</p>
          <p className={`text-2xl font-semibold ${c.color}`}>{c.value}</p>
        </div>
      ))}
    </div>
  );
}
