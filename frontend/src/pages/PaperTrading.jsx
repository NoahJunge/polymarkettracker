import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { getPositions, getPortfolioSummary, getAllTrades } from "../api/client";
import PortfolioSummary from "../components/PortfolioSummary";

function formatPrice(p) {
  if (p == null) return "—";
  return `${(p * 100).toFixed(1)}¢`;
}

export default function PaperTrading() {
  const navigate = useNavigate();
  const [positions, setPositions] = useState([]);
  const [summary, setSummary] = useState(null);
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [sortField, setSortField] = useState("unrealized_pnl");
  const [sortOrder, setSortOrder] = useState("desc");
  const [tradeSearch, setTradeSearch] = useState("");
  const [showAllTrades, setShowAllTrades] = useState(false);

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

  // Filtered and sorted positions
  const filteredPositions = useMemo(() => {
    let list = positions;
    if (search) {
      const q = search.toLowerCase();
      list = list.filter(
        (p) =>
          (p.question || "").toLowerCase().includes(q) ||
          p.market_id.toLowerCase().includes(q)
      );
    }
    list = [...list].sort((a, b) => {
      const aVal = a[sortField] ?? 0;
      const bVal = b[sortField] ?? 0;
      return sortOrder === "desc" ? bVal - aVal : aVal - bVal;
    });
    return list;
  }, [positions, search, sortField, sortOrder]);

  // Filtered trades
  const filteredTrades = useMemo(() => {
    let list = trades;
    if (tradeSearch) {
      const q = tradeSearch.toLowerCase();
      list = list.filter(
        (t) =>
          (t.market_id || "").toLowerCase().includes(q) ||
          (t.side || "").toLowerCase().includes(q)
      );
    }
    return list;
  }, [trades, tradeSearch]);

  const displayedTrades = showAllTrades
    ? filteredTrades
    : filteredTrades.slice(0, 100);

  const handleSort = (field) => {
    if (sortField === field) {
      setSortOrder(sortOrder === "desc" ? "asc" : "desc");
    } else {
      setSortField(field);
      setSortOrder("desc");
    }
  };

  const SortIcon = ({ field }) => {
    if (sortField !== field) return <span className="ml-1 text-slate-300">↕</span>;
    return <span className="ml-1">{sortOrder === "asc" ? "▲" : "▼"}</span>;
  };

  const handleClose = async (pos) => {
    if (!confirm(`Close ${pos.net_quantity} ${pos.side} shares of this position?`))
      return;
    try {
      const { closeTrade } = await import("../api/client");
      await closeTrade({
        market_id: pos.market_id,
        side: pos.side,
        quantity: pos.net_quantity,
      });
      load();
    } catch (err) {
      alert(err.response?.data?.detail || "Failed to close position");
    }
  };

  if (loading) return <p className="text-slate-500">Loading...</p>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Paper Trading</h2>
        <button
          onClick={load}
          className="text-sm px-3 py-1.5 bg-slate-100 text-slate-600 rounded hover:bg-slate-200"
        >
          Refresh
        </button>
      </div>

      {/* Portfolio Summary */}
      <PortfolioSummary summary={summary} />

      {/* Open Positions */}
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-base font-semibold">
            Open Positions ({filteredPositions.length}
            {search ? ` of ${positions.length}` : ""})
          </h3>
          <input
            type="text"
            placeholder="Search positions..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="border border-slate-300 rounded px-3 py-1.5 text-sm w-64"
          />
        </div>

        {filteredPositions.length === 0 ? (
          <p className="text-slate-500 text-sm py-4">
            {search ? "No positions match your search." : "No open positions."}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-slate-500">
                  <th className="pb-2 pr-2 font-medium w-10 text-slate-400">#</th>
                  <th className="pb-2 pr-4 font-medium">Market</th>
                  <th className="pb-2 pr-4 font-medium">Side</th>
                  <th
                    className="pb-2 pr-4 font-medium cursor-pointer select-none hover:text-slate-800"
                    onClick={() => handleSort("net_quantity")}
                  >
                    Qty
                    <SortIcon field="net_quantity" />
                  </th>
                  <th
                    className="pb-2 pr-4 font-medium cursor-pointer select-none hover:text-slate-800"
                    onClick={() => handleSort("avg_entry_price")}
                  >
                    Avg Entry
                    <SortIcon field="avg_entry_price" />
                  </th>
                  <th className="pb-2 pr-4 font-medium">Current</th>
                  <th
                    className="pb-2 pr-4 font-medium cursor-pointer select-none hover:text-slate-800"
                    onClick={() => handleSort("market_value")}
                  >
                    Value
                    <SortIcon field="market_value" />
                  </th>
                  <th
                    className="pb-2 pr-4 font-medium cursor-pointer select-none hover:text-slate-800"
                    onClick={() => handleSort("unrealized_pnl")}
                  >
                    P&L
                    <SortIcon field="unrealized_pnl" />
                  </th>
                  <th className="pb-2 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {filteredPositions.map((p, i) => (
                  <tr key={i} className="border-b border-slate-100 hover:bg-slate-50">
                    <td className="py-2 pr-2 text-xs text-slate-400 font-mono">
                      {i + 1}
                    </td>
                    <td
                      className="py-2 pr-4 max-w-xs cursor-pointer hover:text-blue-600"
                      onClick={() => navigate(`/markets/${p.market_id}`)}
                    >
                      <span className="line-clamp-1">
                        {p.question || p.market_id}
                      </span>
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
                      {formatPrice(p.avg_entry_price)}
                    </td>
                    <td className="py-2 pr-4 font-mono">
                      {formatPrice(p.current_price)}
                    </td>
                    <td className="py-2 pr-4 font-mono">
                      ${p.market_value.toFixed(2)}
                    </td>
                    <td
                      className={`py-2 pr-4 font-mono ${
                        p.unrealized_pnl >= 0 ? "text-green-600" : "text-red-600"
                      }`}
                    >
                      {p.unrealized_pnl >= 0 ? "+" : ""}${p.unrealized_pnl.toFixed(
                        2
                      )}{" "}
                      ({p.unrealized_pnl_pct.toFixed(1)}%)
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
        )}
      </div>

      {/* Trade History */}
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-base font-semibold">
            Trade History ({filteredTrades.length}
            {tradeSearch ? ` of ${trades.length}` : ""} trades)
          </h3>
          <input
            type="text"
            placeholder="Search trades..."
            value={tradeSearch}
            onChange={(e) => setTradeSearch(e.target.value)}
            className="border border-slate-300 rounded px-3 py-1.5 text-sm w-64"
          />
        </div>

        {filteredTrades.length === 0 ? (
          <p className="text-slate-500 text-sm">No trades found.</p>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-white">
                  <tr className="border-b border-slate-200 text-left text-slate-500">
                    <th className="pb-2 pr-4 font-medium">Date</th>
                    <th className="pb-2 pr-4 font-medium">Action</th>
                    <th className="pb-2 pr-4 font-medium">Side</th>
                    <th className="pb-2 pr-4 font-medium">Market</th>
                    <th className="pb-2 pr-4 font-medium">Qty</th>
                    <th className="pb-2 pr-4 font-medium">Price</th>
                    <th className="pb-2 font-medium">DCA</th>
                  </tr>
                </thead>
                <tbody>
                  {displayedTrades.map((t, i) => (
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
                            t.side === "YES"
                              ? "text-green-600"
                              : "text-red-600"
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
                      <td className="py-1.5 pr-4 font-mono">
                        {(t.price * 100).toFixed(1)}¢
                      </td>
                      <td className="py-1.5">
                        {t.metadata?.dca && (
                          <span className="text-xs px-1.5 py-0.5 bg-indigo-100 text-indigo-700 rounded">
                            DCA
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!showAllTrades && filteredTrades.length > 100 && (
              <button
                onClick={() => setShowAllTrades(true)}
                className="mt-3 text-sm text-blue-600 hover:text-blue-800 underline"
              >
                Show all {filteredTrades.length} trades (showing first 100)
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
}
