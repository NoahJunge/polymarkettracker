import { useState, useEffect, useRef, useCallback } from "react";
import {
  getMarkets,
  getCategories,
  getDashboardSummary,
  getPortfolioSummary,
} from "../api/client";
import MarketTable from "../components/MarketTable";
import SummaryCards from "../components/SummaryCards";

const REFRESH_INTERVAL = 60000; // 60 seconds

export default function Dashboard() {
  const [markets, setMarkets] = useState([]);
  const [total, setTotal] = useState(0);
  const [categories, setCategories] = useState([]);
  const [summary, setSummary] = useState(null);
  const [portfolio, setPortfolio] = useState(null);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [sortField, setSortField] = useState("volumeNum");
  const [sortOrder, setSortOrder] = useState("desc");
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [secondsAgo, setSecondsAgo] = useState(0);
  const intervalRef = useRef(null);
  const tickRef = useRef(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {
        tracked: true,
        size: 200,
        sort: sortField,
        order: sortOrder,
      };
      if (search) params.search = search;
      if (category) params.category = category;

      const [marketsRes, summaryRes, portfolioRes] = await Promise.all([
        getMarkets(params),
        getDashboardSummary(),
        getPortfolioSummary().catch(() => ({ data: null })),
      ]);

      setMarkets(marketsRes.data.markets);
      setTotal(marketsRes.data.total);
      setSummary(summaryRes.data);
      setPortfolio(portfolioRes.data);
      setLastUpdated(new Date());
      setSecondsAgo(0);
    } catch (err) {
      console.error("Failed to load markets", err);
    } finally {
      setLoading(false);
    }
  }, [search, category, sortField, sortOrder]);

  const loadCategories = async () => {
    try {
      const res = await getCategories();
      setCategories(res.data);
    } catch (err) {
      console.error("Failed to load categories", err);
    }
  };

  // Initial load
  useEffect(() => {
    loadCategories();
    load();
  }, []);

  // Reload on filter/sort changes
  useEffect(() => {
    load();
  }, [category, sortField, sortOrder]);

  // Auto-refresh polling
  useEffect(() => {
    intervalRef.current = setInterval(() => {
      load();
    }, REFRESH_INTERVAL);
    return () => clearInterval(intervalRef.current);
  }, [load]);

  // Seconds-ago ticker
  useEffect(() => {
    tickRef.current = setInterval(() => {
      if (lastUpdated) {
        setSecondsAgo(Math.floor((Date.now() - lastUpdated.getTime()) / 1000));
      }
    }, 1000);
    return () => clearInterval(tickRef.current);
  }, [lastUpdated]);

  const handleSearch = (e) => {
    e.preventDefault();
    load();
  };

  const handleSort = (field, order) => {
    setSortField(field);
    setSortOrder(order);
  };

  const formatAgo = () => {
    if (!lastUpdated) return "";
    if (secondsAgo < 5) return "just now";
    if (secondsAgo < 60) return `${secondsAgo}s ago`;
    return `${Math.floor(secondsAgo / 60)}m ago`;
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-xl font-semibold">Tracked Markets</h2>
          <p className="text-sm text-slate-500">{total} markets tracked</p>
        </div>
        <div className="flex items-center gap-3">
          {lastUpdated && (
            <span className="text-xs text-slate-400">
              Updated {formatAgo()}
            </span>
          )}
          <button
            onClick={load}
            disabled={loading}
            className="text-sm px-3 py-1.5 bg-slate-100 text-slate-600 rounded hover:bg-slate-200 disabled:opacity-50"
          >
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <SummaryCards summary={summary} portfolio={portfolio} />

      {/* Search and Category Filter */}
      <div className="flex flex-wrap items-end gap-3 mb-4">
        <form onSubmit={handleSearch} className="flex gap-2">
          <input
            type="text"
            placeholder="Search markets..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="border border-slate-300 rounded px-3 py-1.5 text-sm w-64"
          />
          <button
            type="submit"
            className="px-3 py-1.5 bg-slate-800 text-white text-sm rounded hover:bg-slate-900"
          >
            Search
          </button>
        </form>

        <div className="flex items-center gap-2">
          <label className="text-sm text-slate-500">Category:</label>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="border border-slate-300 rounded px-3 py-1.5 text-sm"
          >
            <option value="">All</option>
            {categories.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>
        </div>

        {(search || category) && (
          <button
            onClick={() => {
              setSearch("");
              setCategory("");
              setTimeout(load, 0);
            }}
            className="text-sm text-slate-500 hover:text-slate-700 underline"
          >
            Clear filters
          </button>
        )}
      </div>

      {loading && markets.length === 0 ? (
        <p className="text-slate-500">Loading...</p>
      ) : (
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <MarketTable
            markets={markets}
            sortField={sortField}
            sortOrder={sortOrder}
            onSort={handleSort}
          />
        </div>
      )}
    </div>
  );
}
