function SkeletonBlock({ className }) {
  return <div className={`animate-pulse bg-slate-200 rounded ${className}`} />;
}

export function CardSkeleton() {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-4">
      <SkeletonBlock className="h-4 w-24 mb-3" />
      <div className="space-y-2">
        <div className="flex justify-between">
          <SkeletonBlock className="h-3 w-32" />
          <SkeletonBlock className="h-3 w-12" />
        </div>
        <div className="flex justify-between">
          <SkeletonBlock className="h-3 w-28" />
          <SkeletonBlock className="h-3 w-16" />
        </div>
        <div className="flex justify-between">
          <SkeletonBlock className="h-3 w-24" />
          <SkeletonBlock className="h-3 w-14" />
        </div>
      </div>
    </div>
  );
}

export function TableSkeleton({ rows = 5 }) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-4">
      {/* Header row */}
      <div className="flex gap-4 mb-3 pb-2 border-b border-slate-100">
        <SkeletonBlock className="h-3 w-40" />
        <SkeletonBlock className="h-3 w-16" />
        <SkeletonBlock className="h-3 w-16" />
        <SkeletonBlock className="h-3 w-20" />
      </div>
      {/* Data rows */}
      <div className="space-y-3">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="flex gap-4 items-center">
            <SkeletonBlock className="h-3 w-48" />
            <SkeletonBlock className="h-3 w-14" />
            <SkeletonBlock className="h-3 w-14" />
            <SkeletonBlock className="h-3 w-18" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function ChartSkeleton() {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-4">
      <SkeletonBlock className="h-4 w-32 mb-4" />
      <SkeletonBlock className="h-48 w-full" />
    </div>
  );
}
