function formatTs(ts) {
  return new Date(ts).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export default function SnapshotTable({ snapshots }) {
  if (!snapshots || snapshots.length === 0) {
    return <p className="text-slate-500 py-4">No snapshots yet.</p>;
  }

  return (
    <div className="overflow-x-auto max-h-96 overflow-y-auto">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-white">
          <tr className="border-b border-slate-200 text-left text-slate-500">
            <th className="pb-2 pr-4 font-medium">Timestamp</th>
            <th className="pb-2 pr-4 font-medium">Yes</th>
            <th className="pb-2 pr-4 font-medium">No</th>
            <th className="pb-2 pr-4 font-medium">Spread</th>
            <th className="pb-2 pr-4 font-medium">Volume</th>
            <th className="pb-2 font-medium">Liquidity</th>
          </tr>
        </thead>
        <tbody>
          {snapshots.map((s, i) => (
            <tr key={i} className="border-b border-slate-100">
              <td className="py-1.5 pr-4 text-xs text-slate-600">
                {formatTs(s.timestamp_utc)}
              </td>
              <td className="py-1.5 pr-4 font-mono text-green-600">
                {s.yes_cents}¢
              </td>
              <td className="py-1.5 pr-4 font-mono text-red-600">
                {s.no_cents}¢
              </td>
              <td className="py-1.5 pr-4 font-mono">
                {(s.spread * 100).toFixed(1)}¢
              </td>
              <td className="py-1.5 pr-4 font-mono text-xs">
                ${(s.volumeNum || 0).toLocaleString()}
              </td>
              <td className="py-1.5 font-mono text-xs">
                ${(s.liquidityNum || 0).toLocaleString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
