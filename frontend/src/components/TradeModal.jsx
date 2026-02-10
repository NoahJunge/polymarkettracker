import { useState } from "react";
import { openTrade } from "../api/client";

export default function TradeModal({ marketId, question, onClose, onSuccess }) {
  const [side, setSide] = useState("YES");
  const [quantity, setQuantity] = useState(10);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await openTrade({ market_id: marketId, side, quantity: Number(quantity) });
      onSuccess?.();
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to open trade");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
        <h3 className="text-lg font-semibold mb-1">Open Paper Trade</h3>
        <p className="text-sm text-slate-500 mb-4 line-clamp-2">{question}</p>

        <form onSubmit={handleSubmit} className="space-y-4">
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

          {error && <p className="text-red-600 text-sm">{error}</p>}

          <div className="flex gap-2 justify-end">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? "Opening..." : "Open Trade"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
