import { useState, useEffect } from "react";
import {
  getDatabaseMarkets,
  getDatabaseSnapshots,
  exportDatabaseXlsx,
} from "../api/client";

const PAGE_SIZE = 50;

function formatPrice(p) {
  if (p == null) return "—";
  return `${(p * 100).toFixed(1)}¢`;
}

function formatTimestamp(ts) {
  if (!ts) return "—";
  try {
    const d = new Date(ts);
    return d.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return ts;
  }
}

function formatVolume(v) {
  if (v == null) return "—";
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(1)}K`;
  return `$${v.toFixed(0)}`;
}

export default function Database() {
  const [markets, setMarkets] = useState([]);
  const [selectedMarket, setSelectedMarket] = useState("");
  const [marketSearch, setMarketSearch] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [snapshots, setSnapshots] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [loaded, setLoaded] = useState(false);

  // Load tracked markets for dropdown
  useEffect(() => {
    const loadMarkets = async () => {
      try {
        const res = await getDatabaseMarkets();
        setMarkets(res.data.markets);
      } catch (err) {
        console.error("Failed to load markets", err);
      }
    };
    loadMarkets();
  }, []);

  const loadSnapshots = async (pageOverride) => {
    setLoading(true);
    const currentPage = pageOverride ?? page;
    try {
      const params = {
        size: PAGE_SIZE,
        from: currentPage * PAGE_SIZE,
      };
      if (selectedMarket) params.market_id = selectedMarket;
      if (fromDate) params.from_date = new Date(fromDate).toISOString();
      if (toDate) {
        const to = new Date(toDate);
        to.setHours(23, 59, 59, 999);
        params.to_date = to.toISOString();
      }
      const res = await getDatabaseSnapshots(params);
      setSnapshots(res.data.snapshots);
      setTotal(res.data.total);
      setLoaded(true);
    } catch (err) {
      console.error("Failed to load snapshots", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (loaded) loadSnapshots();
  }, [page]);

  const handleSearch = (e) => {
    e.preventDefault();
    setPage(0);
    loadSnapshots(0);
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const params = {};
      if (selectedMarket) params.market_id = selectedMarket;
      if (fromDate) params.from_date = new Date(fromDate).toISOString();
      if (toDate) {
        const to = new Date(toDate);
        to.setHours(23, 59, 59, 999);
        params.to_date = to.toISOString();
      }
      const res = await exportDatabaseXlsx(params);

      // Trigger download
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement("a");
      link.href = url;
      const disposition = res.headers["content-disposition"];
      const filename = disposition
        ? disposition.split("filename=")[1]
        : "snapshots.xlsx";
      link.setAttribute("download", filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Export failed", err);
      alert("Export failed. Make sure there is data to export.");
    } finally {
      setExporting(false);
    }
  };

  // Filter markets by search
  const filteredMarkets = marketSearch
    ? markets.filter((m) =>
        m.question.toLowerCase().includes(marketSearch.toLowerCase())
      )
    : markets;

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const from = page * PAGE_SIZE + 1;
  const to = Math.min((page + 1) * PAGE_SIZE, total);

  const selectedQuestion = markets.find(
    (m) => m.market_id === selectedMarket
  )?.question;

  return (
    <div>
      <div className="mb-4">
        <h2 className="text-xl font-semibold">Database</h2>
        <p className="text-sm text-slate-500">
          Browse and export snapshot data for tracked markets.
        </p>
      </div>

      {/* Filters */}
      <form onSubmit={handleSearch} className="space-y-3 mb-6">
        <div className="flex flex-wrap items-end gap-3">
          {/* Market selector */}
          <div className="flex flex-col gap-1">
            <label className="text-xs text-slate-500 font-medium">Market</label>
            <div className="relative">
              <input
                type="text"
                placeholder="Search tracked markets..."
                value={marketSearch}
                onChange={(e) => setMarketSearch(e.target.value)}
                className="border border-slate-300 rounded px-3 py-1.5 text-sm w-80"
              />
              {marketSearch && filteredMarkets.length > 0 && (
                <div className="absolute z-10 mt-1 w-full bg-white border border-slate-200 rounded shadow-lg max-h-60 overflow-y-auto">
                  {filteredMarkets.slice(0, 20).map((m) => (
                    <button
                      key={m.market_id}
                      type="button"
                      onClick={() => {
                        setSelectedMarket(m.market_id);
                        setMarketSearch(m.question);
                      }}
                      className="block w-full text-left px-3 py-2 text-sm hover:bg-slate-50 border-b border-slate-100 last:border-0"
                    >
                      {m.question}
                    </button>
                  ))}
                </div>
              )}
            </div>
            {selectedMarket && (
              <button
                type="button"
                onClick={() => {
                  setSelectedMarket("");
                  setMarketSearch("");
                }}
                className="text-xs text-slate-500 hover:text-slate-700 underline self-start"
              >
                Clear selection
              </button>
            )}
          </div>

          {/* Date range */}
          <div className="flex flex-col gap-1">
            <label className="text-xs text-slate-500 font-medium">From</label>
            <input
              type="date"
              value={fromDate}
              onChange={(e) => setFromDate(e.target.value)}
              className="border border-slate-300 rounded px-3 py-1.5 text-sm"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-slate-500 font-medium">To</label>
            <input
              type="date"
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
              className="border border-slate-300 rounded px-3 py-1.5 text-sm"
            />
          </div>

          <button
            type="submit"
            className="px-4 py-1.5 bg-slate-800 text-white text-sm rounded hover:bg-slate-900"
          >
            Search
          </button>

          {(selectedMarket || fromDate || toDate) && (
            <button
              type="button"
              onClick={() => {
                setSelectedMarket("");
                setMarketSearch("");
                setFromDate("");
                setToDate("");
                setSnapshots([]);
                setTotal(0);
                setLoaded(false);
              }}
              className="text-sm text-slate-500 hover:text-slate-700 underline"
            >
              Clear all
            </button>
          )}
        </div>
      </form>

      {/* Export button */}
      {loaded && (
        <div className="flex items-center justify-between mb-4">
          <p className="text-sm text-slate-500">
            {total.toLocaleString()} snapshot{total !== 1 ? "s" : ""} found
            {selectedQuestion && (
              <span>
                {" "}for <span className="font-medium text-slate-700">{selectedQuestion}</span>
              </span>
            )}
          </p>
          <button
            onClick={handleExport}
            disabled={exporting || total === 0}
            className="px-4 py-1.5 bg-green-600 text-white text-sm rounded font-medium hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {exporting ? "Exporting..." : "Export to Excel"}
          </button>
        </div>
      )}

      {/* Snapshots table */}
      {loading && snapshots.length === 0 ? (
        <p className="text-slate-500">Loading...</p>
      ) : loaded ? (
        <>
          <div className="bg-white rounded-lg border border-slate-200 p-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-slate-500">
                  <th className="pb-2 pr-4 font-medium">Timestamp</th>
                  <th className="pb-2 pr-4 font-medium">Market</th>
                  <th className="pb-2 pr-4 font-medium w-20">Yes</th>
                  <th className="pb-2 pr-4 font-medium w-20">No</th>
                  <th className="pb-2 pr-4 font-medium w-20">Spread</th>
                  <th className="pb-2 pr-4 font-medium w-24">Volume</th>
                </tr>
              </thead>
              <tbody>
                {snapshots.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-slate-400">
                      No snapshots found. Try adjusting your filters.
                    </td>
                  </tr>
                ) : (
                  snapshots.map((s, i) => (
                    <tr
                      key={`${s.market_id}-${s.timestamp_utc}-${i}`}
                      className="border-b border-slate-100 hover:bg-slate-50"
                    >
                      <td className="py-2 pr-4 text-slate-600 whitespace-nowrap">
                        {formatTimestamp(s.timestamp_utc)}
                      </td>
                      <td className="py-2 pr-4 max-w-xs">
                        <span className="line-clamp-1">{s.question || s.market_id}</span>
                      </td>
                      <td className="py-2 pr-4 font-mono text-green-600">
                        {formatPrice(s.yes_price)}
                      </td>
                      <td className="py-2 pr-4 font-mono text-red-600">
                        {formatPrice(s.no_price)}
                      </td>
                      <td className="py-2 pr-4 font-mono text-slate-500">
                        {s.spread != null ? `${(s.spread * 100).toFixed(1)}¢` : "—"}
                      </td>
                      <td className="py-2 pr-4 font-mono">
                        {formatVolume(s.volumeNum)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-4">
              <p className="text-sm text-slate-500">
                Showing {from}–{to} of {total.toLocaleString()}
              </p>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                  className="px-3 py-1.5 text-sm border border-slate-300 rounded hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Previous
                </button>
                <span className="text-sm text-slate-600">
                  Page {page + 1} of {totalPages}
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                  disabled={page >= totalPages - 1}
                  className="px-3 py-1.5 text-sm border border-slate-300 rounded hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="bg-white rounded-lg border border-slate-200 p-8 text-center text-slate-400">
          Select a market or date range and click Search to browse snapshot data.
        </div>
      )}
    </div>
  );
}
