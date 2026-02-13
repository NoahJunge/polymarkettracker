import { useState, useEffect } from "react";
import { getNewBets, getCategories, setTracking, exportNewBets } from "../api/client";
import MarketTable from "../components/MarketTable";

const PAGE_SIZE = 50;

export default function Discovery() {
  const [markets, setMarkets] = useState([]);
  const [total, setTotal] = useState(0);
  const [categories, setCategories] = useState([]);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [sortField, setSortField] = useState("volumeNum");
  const [sortOrder, setSortOrder] = useState("desc");
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);

  const load = async (pageOverride) => {
    setLoading(true);
    const currentPage = pageOverride ?? page;
    try {
      const params = {
        size: PAGE_SIZE,
        from: currentPage * PAGE_SIZE,
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
  }, [category, sortField, sortOrder, page]);

  const handleSearch = (e) => {
    e.preventDefault();
    setPage(0);
    load(0);
  };

  const handleSort = (field, order) => {
    setSortField(field);
    setSortOrder(order);
    setPage(0);
  };

  const handleTrack = async (marketId) => {
    try {
      await setTracking(marketId, { is_tracked: true });
      await load();
    } catch (err) {
      console.error("Failed to track market", err);
    }
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const res = await exportNewBets();
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement("a");
      link.href = url;
      const disposition = res.headers["content-disposition"];
      const filename = disposition
        ? disposition.split("filename=")[1]
        : "discovery.xlsx";
      link.setAttribute("download", filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Export failed", err);
      alert("Export failed.");
    } finally {
      setExporting(false);
    }
  };

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const from = page * PAGE_SIZE + 1;
  const to = Math.min((page + 1) * PAGE_SIZE, total);

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
            onChange={(e) => {
              setCategory(e.target.value);
              setPage(0);
            }}
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
              setPage(0);
              setTimeout(() => load(0), 0);
            }}
            className="text-sm text-slate-500 hover:text-slate-700 underline"
          >
            Clear filters
          </button>
        )}

        <button
          onClick={handleExport}
          disabled={exporting || total === 0}
          className="ml-auto px-3 py-1.5 bg-indigo-600 text-white text-sm rounded hover:bg-indigo-700 disabled:opacity-50"
        >
          {exporting ? "Exporting..." : "Export to Excel"}
        </button>
      </div>

      {loading && markets.length === 0 ? (
        <p className="text-slate-500">Loading...</p>
      ) : (
        <>
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
      )}
    </div>
  );
}
