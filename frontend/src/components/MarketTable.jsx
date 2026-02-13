import { useNavigate } from "react-router-dom";

function formatPrice(price) {
  if (price == null) return "—";
  return `${(price * 100).toFixed(1)}¢`;
}

function formatVolume(v) {
  if (v == null) return "—";
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(1)}K`;
  return `$${v.toFixed(0)}`;
}

function formatDate(dateStr) {
  if (!dateStr) return "—";
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return "—";
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return "—";
  }
}

function formatChange(change) {
  if (change == null || change === 0) return <span className="text-slate-400">0%</span>;
  const pct = Math.abs(change * 100).toFixed(1);
  if (change > 0) {
    return <span className="text-green-600">▲ +{pct}%</span>;
  }
  return <span className="text-red-600">▼ -{pct}%</span>;
}

const COLUMNS = [
  { key: "question", label: "Market", sortable: false },
  { key: "yes_price", label: "Yes", sortable: false, width: "w-20" },
  { key: "no_price", label: "No", sortable: false, width: "w-20" },
  { key: "one_day_price_change", label: "24h", sortable: true, width: "w-20" },
  { key: "volumeNum", label: "Volume", sortable: true, width: "w-24" },
  { key: "liquidityNum", label: "Liquidity", sortable: true, width: "w-24" },
  { key: "end_date", label: "End Date", sortable: true, width: "w-28" },
  { key: "status", label: "Status", sortable: false, width: "w-16" },
];

function SortIcon({ active, direction }) {
  if (!active) {
    return <span className="ml-1 text-slate-300">↕</span>;
  }
  return (
    <span className="ml-1">
      {direction === "asc" ? "▲" : "▼"}
    </span>
  );
}

export default function MarketTable({
  markets,
  onTrack,
  showTrackButton = false,
  sortField = "",
  sortOrder = "desc",
  onSort,
  positions = [],
}) {
  const navigate = useNavigate();

  // Build a lookup: market_id -> position data
  const posMap = {};
  for (const p of positions) {
    if (!posMap[p.market_id]) {
      posMap[p.market_id] = p;
    }
  }
  const showBetCol = positions.length > 0;

  const handleHeaderClick = (col) => {
    if (!col.sortable || !onSort) return;
    const newOrder =
      sortField === col.key && sortOrder === "desc" ? "asc" : "desc";
    onSort(col.key, newOrder);
  };

  if (!markets || markets.length === 0) {
    return <p className="text-slate-500 py-4">No markets found.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-left text-slate-500">
            {COLUMNS.map((col) => (
              <th
                key={col.key}
                className={`pb-2 pr-4 font-medium ${col.width || ""} ${
                  col.sortable && onSort
                    ? "cursor-pointer select-none hover:text-slate-800"
                    : ""
                }`}
                onClick={() => handleHeaderClick(col)}
              >
                {col.label}
                {col.sortable && onSort && (
                  <SortIcon
                    active={sortField === col.key}
                    direction={sortOrder}
                  />
                )}
              </th>
            ))}
            {showBetCol && <th className="pb-2 font-medium w-28">Bet</th>}
            {showTrackButton && <th className="pb-2 font-medium w-20"></th>}
          </tr>
        </thead>
        <tbody>
          {markets.map((m) => (
            <tr
              key={m.market_id}
              className="border-b border-slate-100 hover:bg-slate-50 cursor-pointer"
              onClick={() => navigate(`/markets/${m.market_id}`)}
            >
              <td className="py-2.5 pr-4 max-w-md">
                <span className="line-clamp-2">{m.question || m.market_id}</span>
              </td>
              <td className="py-2.5 pr-4 font-mono text-green-600">
                {formatPrice(m.yes_price)}
              </td>
              <td className="py-2.5 pr-4 font-mono text-red-600">
                {formatPrice(m.no_price)}
              </td>
              <td className="py-2.5 pr-4 font-mono text-xs">
                {formatChange(m.one_day_price_change)}
              </td>
              <td className="py-2.5 pr-4 font-mono">
                {formatVolume(m.volumeNum)}
              </td>
              <td className="py-2.5 pr-4 font-mono">
                {formatVolume(m.liquidityNum)}
              </td>
              <td className="py-2.5 pr-4 text-slate-600">
                {formatDate(m.end_date)}
              </td>
              <td className="py-2.5">
                {m.closed ? (
                  <span className="text-xs px-1.5 py-0.5 bg-slate-200 text-slate-600 rounded">
                    Closed
                  </span>
                ) : m.active ? (
                  <span className="text-xs px-1.5 py-0.5 bg-green-100 text-green-700 rounded">
                    Active
                  </span>
                ) : (
                  <span className="text-xs px-1.5 py-0.5 bg-yellow-100 text-yellow-700 rounded">
                    Inactive
                  </span>
                )}
              </td>
              {showBetCol && (
                <td className="py-2.5 pr-4">
                  {posMap[m.market_id] ? (
                    <span
                      className={`text-xs font-medium ${
                        posMap[m.market_id].unrealized_pnl >= 0
                          ? "text-green-600"
                          : "text-red-600"
                      }`}
                    >
                      {posMap[m.market_id].unrealized_pnl >= 0 ? "+" : ""}
                      ${posMap[m.market_id].unrealized_pnl.toFixed(2)}{" "}
                      ({posMap[m.market_id].unrealized_pnl_pct >= 0 ? "+" : ""}
                      {posMap[m.market_id].unrealized_pnl_pct.toFixed(1)}%)
                    </span>
                  ) : (
                    <span className="text-xs text-slate-300">&mdash;</span>
                  )}
                </td>
              )}
              {showTrackButton && (
                <td className="py-2.5">
                  <button
                    className="text-xs px-2 py-1 bg-blue-600 text-white rounded hover:bg-blue-700"
                    onClick={(e) => {
                      e.stopPropagation();
                      onTrack?.(m.market_id);
                    }}
                  >
                    Track
                  </button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
