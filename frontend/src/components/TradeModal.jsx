import { useState } from "react";
import { openTrade, createDCA } from "../api/client";

export default function TradeModal({ marketId, question, onClose, onSuccess }) {
  const [side, setSide] = useState("YES");
  const [quantity, setQuantity] = useState(1);
  const [dcaMode, setDcaMode] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccessMsg(null);
    try {
      if (dcaMode) {
        const res = await createDCA({
          market_id: marketId,
          side,
          quantity: Number(quantity),
        });
        setSuccessMsg(
          `DCA started! ${res.data.trades_backfilled} historical trades placed.`,
        );
        onSuccess?.();
      } else {
        await openTrade({
          market_id: marketId,
          side,
          quantity: Number(quantity),
        });
        onSuccess?.();
        onClose();
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to place trade");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
        <h3 className="text-lg font-semibold mb-1">
          {dcaMode ? "Start DCA Strategy" : "Open Paper Trade"}
        </h3>
        <p className="text-sm text-slate-500 mb-4 line-clamp-2">{question}</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Side selector */}
          <div>
            <label className="block text-sm font-medium mb-1">Side</label>
            <div className="flex gap-2">
              <button
                type="button"
                className={`flex-1 py-2 rounded font-medium text-sm ${
                  side === "YES"
                    ? "bg-green-600 text-white"
                    : "bg-slate-100 text-slate-600"
                }`}
                onClick={() => setSide("YES")}
              >
                YES
              </button>
              <button
                type="button"
                className={`flex-1 py-2 rounded font-medium text-sm ${
                  side === "NO"
                    ? "bg-red-600 text-white"
                    : "bg-slate-100 text-slate-600"
                }`}
                onClick={() => setSide("NO")}
              >
                NO
              </button>
            </div>
          </div>

          {/* Quantity */}
          <div>
            <label className="block text-sm font-medium mb-1">
              Quantity (shares)
            </label>
            <input
              type="number"
              min="1"
              step="1"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
            />
          </div>

          {/* DCA Toggle */}
          <div className="border border-slate-200 rounded-lg p-3">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={dcaMode}
                onChange={(e) => {
                  setDcaMode(e.target.checked);
                  setSuccessMsg(null);
                }}
                className="rounded"
              />
              <span className="text-sm font-medium">Recurring DCA</span>
            </label>
            {dcaMode && (
              <p className="text-xs text-slate-500 mt-2">
                Places a daily recurring bet of {quantity || 0} {side} shares.
                Backfills trades from all available historical data, then
                automatically places a new trade each day.
              </p>
            )}
          </div>

          {error && <p className="text-red-600 text-sm">{error}</p>}
          {successMsg && (
            <p className="text-green-600 text-sm bg-green-50 rounded p-2">
              {successMsg}
            </p>
          )}

          <div className="flex gap-2 justify-end">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded"
            >
              {successMsg ? "Close" : "Cancel"}
            </button>
            {!successMsg && (
              <button
                type="submit"
                disabled={loading}
                className={`px-4 py-2 text-sm text-white rounded disabled:opacity-50 ${
                  dcaMode
                    ? "bg-indigo-600 hover:bg-indigo-700"
                    : "bg-blue-600 hover:bg-blue-700"
                }`}
              >
                {loading
                  ? "Processing..."
                  : dcaMode
                    ? "Start DCA"
                    : "Open Trade"}
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}
