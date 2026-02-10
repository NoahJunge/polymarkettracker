import { useNavigate } from "react-router-dom";

function formatChange(change) {
  if (change == null || change === 0) return "0%";
  const pct = (change * 100).toFixed(1);
  const sign = change > 0 ? "+" : "";
  return `${sign}${pct}%`;
}

function formatDate(dateStr) {
  if (!dateStr) return "—";
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return "—";
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return "—";
  }
}

export default function SummaryCards({ summary, portfolio }) {
  const navigate = useNavigate();

  if (!summary) return null;

  const { total_tracked, total_discovered, biggest_movers, closing_soon } =
    summary;

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
      {/* Overview Card */}
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <h3 className="text-sm font-medium text-slate-500 mb-3">Overview</h3>
        <div className="space-y-2">
          <div className="flex justify-between">
            <span className="text-sm text-slate-600">Tracked Markets</span>
            <span className="text-sm font-semibold">{total_tracked}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-sm text-slate-600">Total Discovered</span>
            <span className="text-sm font-semibold">{total_discovered}</span>
          </div>
          {portfolio && (
            <>
              <div className="border-t border-slate-100 pt-2 mt-2">
                <div className="flex justify-between">
                  <span className="text-sm text-slate-600">Unrealized P&L</span>
                  <span
                    className={`text-sm font-semibold ${
                      (portfolio.unrealized_pnl || 0) >= 0
                        ? "text-green-600"
                        : "text-red-600"
                    }`}
                  >
                    ${(portfolio.unrealized_pnl || 0).toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-slate-600">Realized P&L</span>
                  <span
                    className={`text-sm font-semibold ${
                      (portfolio.realized_pnl || 0) >= 0
                        ? "text-green-600"
                        : "text-red-600"
                    }`}
                  >
                    ${(portfolio.realized_pnl || 0).toFixed(2)}
                  </span>
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Biggest Movers Card */}
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <h3 className="text-sm font-medium text-slate-500 mb-3">
          Biggest Movers (24h)
        </h3>
        {biggest_movers && biggest_movers.length > 0 ? (
          <div className="space-y-1.5">
            {biggest_movers.map((m) => (
              <div
                key={m.market_id}
                className="flex items-center justify-between cursor-pointer hover:bg-slate-50 rounded px-1 -mx-1"
                onClick={() => navigate(`/markets/${m.market_id}`)}
              >
                <span className="text-sm text-slate-700 truncate max-w-[180px]">
                  {m.question}
                </span>
                <span
                  className={`text-sm font-mono font-semibold ml-2 whitespace-nowrap ${
                    (m.one_day_price_change || 0) >= 0
                      ? "text-green-600"
                      : "text-red-600"
                  }`}
                >
                  {(m.one_day_price_change || 0) >= 0 ? "▲" : "▼"}{" "}
                  {formatChange(m.one_day_price_change)}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-400">No data yet</p>
        )}
      </div>

      {/* Closing Soon Card */}
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <h3 className="text-sm font-medium text-slate-500 mb-3">
          Closing Soon
        </h3>
        {closing_soon && closing_soon.length > 0 ? (
          <div className="space-y-1.5">
            {closing_soon.map((m) => (
              <div
                key={m.market_id}
                className="flex items-center justify-between cursor-pointer hover:bg-slate-50 rounded px-1 -mx-1"
                onClick={() => navigate(`/markets/${m.market_id}`)}
              >
                <span className="text-sm text-slate-700 truncate max-w-[180px]">
                  {m.question}
                </span>
                <span className="text-xs text-orange-600 font-medium ml-2 whitespace-nowrap">
                  {m.days_until_close != null
                    ? `${m.days_until_close}d left`
                    : formatDate(m.end_date)}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-400">No markets closing soon</p>
        )}
      </div>
    </div>
  );
}
