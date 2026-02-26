import { useState } from "react";
import { getMonteCarlo } from "../api/client";
import MonteCarloChart from "./MonteCarloChart";

export default function MonteCarloSection() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [iterations, setIterations] = useState(10000);
  const [error, setError] = useState(null);

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getMonteCarlo({ iterations });
      setData(res.data);
    } catch (err) {
      setError("Simulation failed. Please try again.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // Find the optimal percentage (highest prob_positive)
  const optimal = data?.results?.reduce(
    (best, r) => (!best || r.prob_positive > best.prob_positive ? r : best),
    null
  );

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4">
      {/* Header row */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-base font-semibold">Monte Carlo Simulation</h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Randomly sample X% of tracked markets and compute total portfolio P&L,
            repeated N times. Answers: "What if only 70/80/90% of events existed?"
          </p>
        </div>
        <div className="flex items-center gap-3 shrink-0 ml-4">
          <label className="text-sm text-slate-600 flex items-center gap-1.5">
            Iterations:
            <select
              value={iterations}
              onChange={(e) => setIterations(Number(e.target.value))}
              className="border border-slate-300 rounded px-2 py-1 text-sm"
            >
              <option value={1000}>1,000</option>
              <option value={5000}>5,000</option>
              <option value={10000}>10,000</option>
              <option value={50000}>50,000</option>
            </select>
          </label>
          <button
            onClick={run}
            disabled={loading}
            className="text-sm px-4 py-1.5 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 whitespace-nowrap"
          >
            {loading ? "Running..." : "Run Simulation"}
          </button>
        </div>
      </div>

      {error && (
        <p className="text-red-500 text-sm mb-3">{error}</p>
      )}

      {loading && (
        <div className="text-center py-10 text-slate-500 text-sm">
          Running {iterations.toLocaleString()} iterations across 70%, 80%, 90% subsets…
        </div>
      )}

      {data && !loading && (
        <>
          {/* Summary banner */}
          <div className="flex items-center gap-4 mb-4 px-3 py-2 bg-slate-100 rounded text-sm">
            <span className="text-slate-600">
              Pool: <strong>{data.total_markets}</strong> markets with P&L data
            </span>
            <span className="text-slate-400">·</span>
            <span className="text-slate-600">
              Iterations: <strong>{data.iterations.toLocaleString()}</strong>
            </span>
            {optimal && (
              <>
                <span className="text-slate-400">·</span>
                <span className="text-slate-600">
                  Optimal subset:{" "}
                  <strong className="text-blue-600">{optimal.percentage}%</strong>
                  {" "}(P(gain) = {(optimal.prob_positive * 100).toFixed(1)}%)
                </span>
              </>
            )}
          </div>

          {/* Three histograms */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {data.results.map((r) => (
              <MonteCarloChart key={r.percentage} result={r} />
            ))}
          </div>
        </>
      )}

      {!data && !loading && (
        <p className="text-slate-400 text-sm text-center py-8">
          Click "Run Simulation" to compute the distribution of portfolio P&L outcomes
          across random subsets of tracked markets.
        </p>
      )}
    </div>
  );
}
