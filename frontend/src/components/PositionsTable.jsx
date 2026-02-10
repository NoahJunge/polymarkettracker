import { useNavigate } from "react-router-dom";
import { closeTrade } from "../api/client";

export default function PositionsTable({ positions, onUpdate }) {
  const navigate = useNavigate();

  const handleClose = async (pos) => {
    if (!confirm(`Close ${pos.net_quantity} ${pos.side} shares of this position?`))
      return;
    try {
      await closeTrade({
        market_id: pos.market_id,
        side: pos.side,
        quantity: pos.net_quantity,
      });
      onUpdate?.();
    } catch (err) {
      alert(err.response?.data?.detail || "Failed to close position");
    }
  };

  if (!positions || positions.length === 0) {
    return <p className="text-slate-500 py-4">No open positions.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-left text-slate-500">
            <th className="pb-2 pr-4 font-medium">Market</th>
            <th className="pb-2 pr-4 font-medium">Side</th>
            <th className="pb-2 pr-4 font-medium">Qty</th>
            <th className="pb-2 pr-4 font-medium">Avg Entry</th>
            <th className="pb-2 pr-4 font-medium">Current</th>
            <th className="pb-2 pr-4 font-medium">Value</th>
            <th className="pb-2 pr-4 font-medium">P&L</th>
            <th className="pb-2 font-medium"></th>
          </tr>
        </thead>
        <tbody>
          {positions.map((p, i) => (
            <tr key={i} className="border-b border-slate-100">
              <td
                className="py-2 pr-4 max-w-xs cursor-pointer hover:text-blue-600"
                onClick={() => navigate(`/markets/${p.market_id}`)}
              >
                <span className="line-clamp-1">{p.question || p.market_id}</span>
              </td>
              <td className="py-2 pr-4">
                <span
                  className={`text-xs font-medium px-1.5 py-0.5 rounded ${
                    p.side === "YES"
                      ? "bg-green-100 text-green-700"
                      : "bg-red-100 text-red-700"
                  }`}
                >
                  {p.side}
                </span>
              </td>
              <td className="py-2 pr-4 font-mono">{p.net_quantity}</td>
              <td className="py-2 pr-4 font-mono">
                {(p.avg_entry_price * 100).toFixed(1)}¢
              </td>
              <td className="py-2 pr-4 font-mono">
                {(p.current_price * 100).toFixed(1)}¢
              </td>
              <td className="py-2 pr-4 font-mono">
                ${p.market_value.toFixed(2)}
              </td>
              <td
                className={`py-2 pr-4 font-mono ${
                  p.unrealized_pnl >= 0 ? "text-green-600" : "text-red-600"
                }`}
              >
                {p.unrealized_pnl >= 0 ? "+" : ""}
                ${p.unrealized_pnl.toFixed(2)} ({p.unrealized_pnl_pct.toFixed(1)}
                %)
              </td>
              <td className="py-2">
                <button
                  className="text-xs px-2 py-1 bg-slate-200 hover:bg-slate-300 rounded"
                  onClick={() => handleClose(p)}
                >
                  Close
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
