import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { getMarket, getSnapshots, setTracking } from "../api/client";
import PriceChart from "../components/PriceChart";
import SnapshotTable from "../components/SnapshotTable";
import TradeModal from "../components/TradeModal";
import AlertModal from "../components/AlertModal";

export default function MarketDetail() {
  const { marketId } = useParams();
  const [market, setMarket] = useState(null);
  const [snapshots, setSnapshots] = useState([]);
  const [showTradeModal, setShowTradeModal] = useState(false);
  const [showAlertModal, setShowAlertModal] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [mRes, sRes] = await Promise.all([
        getMarket(marketId),
        getSnapshots(marketId, { limit: 2000, sort: "desc" }),
      ]);
      setMarket(mRes.data);
      setSnapshots(sRes.data);
    } catch (err) {
      console.error("Failed to load market", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [marketId]);

  const handleTrack = async () => {
    try {
      await setTracking(marketId, { is_tracked: !market.is_tracked });
      await load();
    } catch (err) {
      console.error("Failed to update tracking", err);
    }
  };

  if (loading) return <p className="text-slate-500">Loading...</p>;
  if (!market) return <p className="text-red-500">Market not found.</p>;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-semibold">{market.question}</h2>
        <div className="flex items-center gap-4 mt-2 text-sm text-slate-500">
          <span>ID: {market.market_id}</span>
          {market.active && !market.closed && (
            <span className="px-1.5 py-0.5 bg-green-100 text-green-700 rounded text-xs">
              Active
            </span>
          )}
          {market.closed && (
            <span className="px-1.5 py-0.5 bg-slate-200 text-slate-600 rounded text-xs">
              Closed
            </span>
          )}
          {market.source_tags?.map((t) => (
            <span
              key={t}
              className="px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded text-xs"
            >
              {t}
            </span>
          ))}
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <p className="text-xs text-slate-500">Yes Price</p>
          <p className="text-2xl font-semibold text-green-600">
            {market.yes_price != null
              ? `${(market.yes_price * 100).toFixed(1)}¢`
              : "—"}
          </p>
        </div>
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <p className="text-xs text-slate-500">No Price</p>
          <p className="text-2xl font-semibold text-red-600">
            {market.no_price != null
              ? `${(market.no_price * 100).toFixed(1)}¢`
              : "—"}
          </p>
        </div>
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <p className="text-xs text-slate-500">Volume</p>
          <p className="text-xl font-semibold">
            ${(market.volumeNum || 0).toLocaleString()}
          </p>
        </div>
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <p className="text-xs text-slate-500">Liquidity</p>
          <p className="text-xl font-semibold">
            ${(market.liquidityNum || 0).toLocaleString()}
          </p>
        </div>
      </div>

      {/* Extra info */}
      {(market.end_date || market.description) && (
        <div className="bg-white rounded-lg border border-slate-200 p-4 space-y-2">
          {market.end_date && (
            <p className="text-sm text-slate-600">
              <span className="font-medium">End Date:</span>{" "}
              {new Date(market.end_date).toLocaleDateString("en-US", {
                month: "long",
                day: "numeric",
                year: "numeric",
              })}
            </p>
          )}
          {market.description && (
            <p className="text-sm text-slate-500 leading-relaxed">
              {market.description}
            </p>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-3">
        <button
          onClick={handleTrack}
          className={`px-4 py-2 text-sm rounded font-medium ${
            market.is_tracked
              ? "bg-slate-200 text-slate-700 hover:bg-slate-300"
              : "bg-blue-600 text-white hover:bg-blue-700"
          }`}
        >
          {market.is_tracked ? "Untrack" : "Track Market"}
        </button>
        <button
          onClick={() => setShowTradeModal(true)}
          className="px-4 py-2 text-sm bg-green-600 text-white rounded font-medium hover:bg-green-700"
        >
          Create Paper Trade
        </button>
        <button
          onClick={() => setShowAlertModal(true)}
          className="px-4 py-2 text-sm bg-orange-500 text-white rounded font-medium hover:bg-orange-600"
        >
          Set Price Alert
        </button>
        {market.polymarket_url && (
          <a
            href={market.polymarket_url}
            target="_blank"
            rel="noopener noreferrer"
            className="px-4 py-2 text-sm border border-slate-300 rounded hover:bg-slate-50"
          >
            View on Polymarket
          </a>
        )}
      </div>

      {/* Price Chart */}
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <h3 className="text-base font-semibold mb-3">Price History</h3>
        <PriceChart snapshots={snapshots} />
      </div>

      {/* Snapshot Table */}
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <h3 className="text-base font-semibold mb-3">
          Snapshots ({snapshots.length})
        </h3>
        <SnapshotTable snapshots={snapshots} />
      </div>

      {/* Trade Modal */}
      {showTradeModal && (
        <TradeModal
          marketId={marketId}
          question={market.question}
          onClose={() => setShowTradeModal(false)}
          onSuccess={load}
        />
      )}

      {/* Alert Modal */}
      {showAlertModal && (
        <AlertModal
          marketId={marketId}
          question={market.question}
          onClose={() => setShowAlertModal(false)}
        />
      )}
    </div>
  );
}
