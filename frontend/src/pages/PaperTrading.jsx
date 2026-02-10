import { useState, useEffect } from "react";
import { getPositions, getPortfolioSummary, getAllTrades } from "../api/client";
import PortfolioSummary from "../components/PortfolioSummary";
import PositionsTable from "../components/PositionsTable";

export default function PaperTrading() {
  const [positions, setPositions] = useState([]);
  const [summary, setSummary] = useState(null);
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [pRes, sRes, tRes] = await Promise.all([
        getPositions(),
        getPortfolioSummary(),
        getAllTrades(),
      ]);
      setPositions(pRes.data);
      setSummary(sRes.data);
      setTrades(tRes.data);
    } catch (err) {
      console.error("Failed to load paper trading data", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  if (loading) return <p className="text-slate-500">Loading...</p>;

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Paper Trading</h2>

      {/* Portfolio Summary */}
      <PortfolioSummary summary={summary} />

      {/* Open Positions */}
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <h3 className="text-base font-semibold mb-3">Open Positions</h3>
        <PositionsTable positions={positions} onUpdate={load} />
      </div>

      {/* Trade History */}
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <h3 className="text-base font-semibold mb-3">
          Trade History ({trades.length} trades)
        </h3>
        {trades.length === 0 ? (
          <p className="text-slate-500 text-sm">No trades yet.</p>
        ) : (
          <div className="overflow-x-auto max-h-80 overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-white">
                <tr className="border-b border-slate-200 text-left text-slate-500">
                  <th className="pb-2 pr-4 font-medium">Date</th>
                  <th className="pb-2 pr-4 font-medium">Action</th>
                  <th className="pb-2 pr-4 font-medium">Side</th>
                  <th className="pb-2 pr-4 font-medium">Market</th>
                  <th className="pb-2 pr-4 font-medium">Qty</th>
                  <th className="pb-2 font-medium">Price</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((t, i) => (
                  <tr key={i} className="border-b border-slate-100">
                    <td className="py-1.5 pr-4 text-xs text-slate-600">
                      {new Date(t.created_at_utc).toLocaleString()}
                    </td>
                    <td className="py-1.5 pr-4">
                      <span
                        className={`text-xs font-medium px-1.5 py-0.5 rounded ${
                          t.action === "OPEN"
                            ? "bg-blue-100 text-blue-700"
                            : "bg-orange-100 text-orange-700"
                        }`}
                      >
                        {t.action}
                      </span>
                    </td>
                    <td className="py-1.5 pr-4">
                      <span
                        className={`text-xs font-medium ${
                          t.side === "YES" ? "text-green-600" : "text-red-600"
                        }`}
                      >
                        {t.side}
                      </span>
                    </td>
                    <td className="py-1.5 pr-4 max-w-xs">
                      <span className="line-clamp-1 text-xs">
                        {t.market_id}
                      </span>
                    </td>
                    <td className="py-1.5 pr-4 font-mono">{t.quantity}</td>
                    <td className="py-1.5 font-mono">
                      {(t.price * 100).toFixed(1)}¢
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
