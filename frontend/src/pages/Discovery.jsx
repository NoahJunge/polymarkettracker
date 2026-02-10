import { useState, useEffect } from "react";
import { getNewBets, getCategories, setTracking } from "../api/client";
import MarketTable from "../components/MarketTable";

export default function Discovery() {
  const [markets, setMarkets] = useState([]);
  const [total, setTotal] = useState(0);
  const [categories, setCategories] = useState([]);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [sortField, setSortField] = useState("volumeNum");
  const [sortOrder, setSortOrder] = useState("desc");
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const params = {
        size: 200,
        sort: sortField,
        order: sortOrder,
      };
      if (search) params.search = search;
      if (category) params.category = category;
      const res = await getNewBets(params);
      setMarkets(res.data.markets);
      setTotal(res.data.total);
    } catch (err) {
      console.error("Failed to load new bets", err);
    } finally {
      setLoading(false);
    }
  };

  const loadCategories = async () => {
    try {
      const res = await getCategories();
      setCategories(res.data);
    } catch (err) {
      console.error("Failed to load categories", err);
    }
  };

  useEffect(() => {
    loadCategories();
    load();
  }, []);

  useEffect(() => {
    load();
  }, [category, sortField, sortOrder]);

  const handleSearch = (e) => {
    e.preventDefault();
    load();
  };

  const handleSort = (field, order) => {
    setSortField(field);
    setSortOrder(order);
  };

  const handleTrack = async (marketId) => {
    try {
      await setTracking(marketId, { is_tracked: true });
      await load();
    } catch (err) {
      console.error("Failed to track market", err);
    }
  };

  return (
    <div>
      <div className="mb-4">
        <h2 className="text-xl font-semibold">New Bets / Discovery</h2>
        <p className="text-sm text-slate-500">
          {total} discovered markets not yet tracked. Click "Track" to start
          collecting snapshots.
        </p>
      </div>

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

      {loading ? (
        <p className="text-slate-500">Loading...</p>
      ) : (
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <MarketTable
            markets={markets}
            showTrackButton
            onTrack={handleTrack}
            sortField={sortField}
            sortOrder={sortOrder}
            onSort={handleSort}
          />
        </div>
      )}
    </div>
  );
}
