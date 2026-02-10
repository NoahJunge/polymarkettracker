import { useState } from "react";
import { createAlert } from "../api/client";

export default function AlertModal({ marketId, question, onClose, onCreated }) {
  const [side, setSide] = useState("YES");
  const [condition, setCondition] = useState("ABOVE");
  const [threshold, setThreshold] = useState("");
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    const value = parseFloat(threshold) / 100; // Convert cents to decimal
    if (isNaN(value) || value < 0 || value > 100) {
      setError("Enter a valid price between 0 and 100 cents");
      return;
    }
    setLoading(true);
    try {
      await createAlert({
        market_id: marketId,
        side,
        condition,
        threshold: value,
        note,
      });
      onCreated?.();
      onClose();
    } catch (err) {
      setError("Failed to create alert");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
        <h3 className="text-lg font-semibold mb-1">Set Price Alert</h3>
        <p className="text-sm text-slate-500 mb-4 truncate">{question}</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="flex gap-3">
            <div className="flex-1">
              <label className="block text-sm text-slate-600 mb-1">Side</label>
              <select
                value={side}
                onChange={(e) => setSide(e.target.value)}
                className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
              >
                <option value="YES">Yes</option>
                <option value="NO">No</option>
              </select>
            </div>
            <div className="flex-1">
              <label className="block text-sm text-slate-600 mb-1">
                Condition
              </label>
              <select
                value={condition}
                onChange={(e) => setCondition(e.target.value)}
                className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
              >
                <option value="ABOVE">Goes above</option>
                <option value="BELOW">Goes below</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm text-slate-600 mb-1">
              Price threshold (in cents, e.g. 50 = 50¢)
            </label>
            <input
              type="number"
              step="0.1"
              min="0"
              max="100"
              value={threshold}
              onChange={(e) => setThreshold(e.target.value)}
              placeholder="e.g. 50"
              className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
              required
            />
          </div>

          <div>
            <label className="block text-sm text-slate-600 mb-1">
              Note (optional)
            </label>
            <input
              type="text"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="e.g. Consider buying if price drops"
              className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
            />
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? "Creating..." : "Create Alert"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
