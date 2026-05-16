/**
 * LoadingSkeleton - Skeleton loader components for dashboard widgets
 * Provides shimmer-like loading states for all major UI sections.
 */
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

// ═── Global shimmer keyframes ────────────────────────────
// Include once in app via main.tsx or App.tsx

// ─── Types ───────────────────────────────────────────────

interface SkeletonCardProps {
  className?: string;
  children?: React.ReactNode;
}

// ─── Reusable Skeleton Parts ─────────────────────────────

export function SkeletonCard({ className, children }: SkeletonCardProps) {
  return (
    <div
      className={cn(
        "bg-white rounded-xl border border-[#E2E8F0] shadow-sm overflow-hidden",
        className
      )}
    >
      {children}
    </div>
  );
}

/** KPI card skeleton */
export function KPICardSkeleton({ index = 0 }: { index?: number }) {
  return (
    <SkeletonCard>
      <div className="p-6 space-y-4">
        {/* Icon + label + trend */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Skeleton className="w-10 h-10 rounded-full" />
            <Skeleton className="w-24 h-4 rounded-md" />
          </div>
          <Skeleton className="w-16 h-6 rounded-full" />
        </div>
        {/* Value */}
        <Skeleton className="w-32 h-8 rounded-md" />
        {/* Period */}
        <Skeleton className="w-28 h-3 rounded-md" />
      </div>
    </SkeletonCard>
  );
}

/** Row of KPI skeletons */
export function KPICardsSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-5">
      {Array.from({ length: count }).map((_, i) => (
        <KPICardSkeleton key={i} index={i} />
      ))}
    </div>
  );
}

/** Chart area skeleton */
export function ChartSkeleton({ className }: { className?: string }) {
  return (
    <SkeletonCard className={className}>
      <div className="p-6 space-y-4">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="space-y-2">
            <Skeleton className="w-40 h-5 rounded-md" />
            <Skeleton className="w-56 h-3 rounded-md" />
          </div>
          <Skeleton className="w-8 h-8 rounded-md" />
        </div>
        {/* Chart area */}
        <div className="space-y-2 pt-4">
          <Skeleton className="w-full h-[180px] rounded-lg" />
        </div>
        {/* Legend */}
        <div className="flex items-center justify-center gap-6 pt-2">
          <Skeleton className="w-20 h-3 rounded-md" />
          <Skeleton className="w-20 h-3 rounded-md" />
        </div>
      </div>
    </SkeletonCard>
  );
}

/** Pie/doughnut chart skeleton */
export function PieChartSkeleton({ className }: { className?: string }) {
  return (
    <SkeletonCard className={className}>
      <div className="p-6 space-y-4">
        <Skeleton className="w-40 h-5 rounded-md mb-1" />
        <Skeleton className="w-56 h-3 rounded-md" />
        {/* Centered circle */}
        <div className="flex justify-center py-4">
          <Skeleton className="w-40 h-40 rounded-full" />
        </div>
        {/* Legend */}
        <div className="flex flex-wrap justify-center gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="w-24 h-3 rounded-md" />
          ))}
        </div>
      </div>
    </SkeletonCard>
  );
}

/** Alert/notification list skeleton */
export function AlertListSkeleton({ count = 4 }: { count?: number }) {
  return (
    <SkeletonCard>
      <div className="p-6 space-y-3">
        <Skeleton className="w-32 h-5 rounded-md mb-1" />
        <Skeleton className="w-48 h-3 rounded-md mb-3" />
        {Array.from({ length: count }).map((_, i) => (
          <div key={i} className="flex gap-3 py-2">
            <Skeleton className="w-8 h-8 rounded-full shrink-0" />
            <div className="flex-1 space-y-2 min-w-0">
              <Skeleton className="w-full h-4 rounded-md" />
              <Skeleton className="w-3/4 h-3 rounded-md" />
            </div>
          </div>
        ))}
      </div>
    </SkeletonCard>
  );
}

/** Table skeleton */
export function TableSkeleton({
  rows = 5,
  columns = 4,
}: {
  rows?: number;
  columns?: number;
}) {
  return (
    <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm overflow-hidden">
      {/* Table header */}
      <div className="border-b border-[#E2E8F0] px-6 py-3">
        <div className="flex gap-4">
          {Array.from({ length: columns }).map((_, i) => (
            <Skeleton
              key={i}
              className={cn(
                "h-4 rounded-md",
                i === 0 ? "w-1/3" : "w-1/4"
              )}
            />
          ))}
        </div>
      </div>
      {/* Table rows */}
      <div className="divide-y divide-[#E2E8F0]">
        {Array.from({ length: rows }).map((_, ri) => (
          <div key={ri} className="px-6 py-4">
            <div className="flex gap-4 items-center">
              {Array.from({ length: columns }).map((_, ci) => (
                <Skeleton
                  key={ci}
                  className={cn(
                    "h-3 rounded-md",
                    ci === 0 ? "w-1/3" : "w-1/4"
                  )}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Card list skeleton (e.g., for mobile table replacement) */
export function CardListSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="bg-white rounded-xl border border-[#E2E8F0] p-4 space-y-3"
        >
          <div className="flex items-center justify-between">
            <Skeleton className="w-1/2 h-4 rounded-md" />
            <Skeleton className="w-16 h-5 rounded-full" />
          </div>
          <Skeleton className="w-3/4 h-3 rounded-md" />
          <div className="flex gap-2 pt-1">
            <Skeleton className="w-20 h-3 rounded-md" />
            <Skeleton className="w-20 h-3 rounded-md" />
          </div>
        </div>
      ))}
    </div>
  );
}

/** AI insight card skeleton */
export function AIInsightSkeleton() {
  return (
    <SkeletonCard>
      <div className="p-6 space-y-4">
        <div className="flex items-center gap-2">
          <Skeleton className="w-5 h-5 rounded-full" />
          <Skeleton className="w-28 h-5 rounded-md" />
          <Skeleton className="w-12 h-5 rounded-full" />
        </div>
        <Skeleton className="w-full h-4 rounded-md" />
        <div className="space-y-2">
          <Skeleton className="w-full h-3 rounded-md" />
          <Skeleton className="w-5/6 h-3 rounded-md" />
        </div>
        <div className="flex items-center gap-3 pt-2">
          <Skeleton className="w-20 h-8 rounded-md" />
          <Skeleton className="w-20 h-8 rounded-md" />
        </div>
      </div>
    </SkeletonCard>
  );
}

/** Sidebar navigation skeleton */
export function SidebarSkeleton() {
  return (
    <div className="w-[260px] h-full bg-[#0F172A] p-4 space-y-6">
      {/* Logo */}
      <div className="flex items-center gap-3 pb-4 border-b border-[#1E293B]">
        <Skeleton className="w-9 h-9 rounded-lg bg-[#334155]" />
        <Skeleton className="w-24 h-5 rounded-md bg-[#334155]" />
      </div>
      {/* Nav sections */}
      {Array.from({ length: 3 }).map((_, si) => (
        <div key={si} className="space-y-2">
          <Skeleton className="w-16 h-3 rounded-md bg-[#334155]" />
          {Array.from({ length: 3 }).map((_, ni) => (
            <Skeleton
              key={ni}
              className="w-full h-9 rounded-lg bg-[#334155]"
            />
          ))}
        </div>
      ))}
      {/* User */}
      <div className="mt-auto pt-4 border-t border-[#1E293B]">
        <div className="flex items-center gap-3">
          <Skeleton className="w-9 h-9 rounded-full bg-[#334155]" />
          <div className="space-y-1">
            <Skeleton className="w-28 h-3 rounded-md bg-[#334155]" />
            <Skeleton className="w-20 h-3 rounded-md bg-[#334155]" />
          </div>
        </div>
      </div>
    </div>
  );
}

/** Full page loading state for dashboard */
export function DashboardSkeleton() {
  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <Skeleton className="w-32 h-7 rounded-md" />
          <Skeleton className="w-56 h-3 rounded-md" />
        </div>
        <div className="flex gap-3">
          <Skeleton className="w-36 h-9 rounded-lg" />
          <Skeleton className="w-9 h-9 rounded-lg" />
        </div>
      </div>

      {/* KPI Cards */}
      <KPICardsSkeleton count={4} />

      {/* Chart */}
      <ChartSkeleton />

      {/* Two-column: Pie + Alerts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <PieChartSkeleton />
        <AlertListSkeleton count={4} />
      </div>

      {/* AI Insight */}
      <AIInsightSkeleton />

      {/* Two-column: Quick Actions + Branch */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <SkeletonCard>
          <div className="p-6 space-y-3">
            <Skeleton className="w-28 h-5 rounded-md mb-3" />
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex items-center gap-3">
                <Skeleton className="w-5 h-5 rounded-md" />
                <Skeleton className="w-full h-4 rounded-md" />
              </div>
            ))}
          </div>
        </SkeletonCard>
        <SkeletonCard>
          <div className="p-6 space-y-4">
            <Skeleton className="w-32 h-5 rounded-md mb-1" />
            <Skeleton className="w-40 h-3 rounded-md mb-2" />
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="space-y-2">
                <div className="flex items-center justify-between">
                  <Skeleton className="w-1/3 h-4 rounded-md" />
                  <Skeleton className="w-16 h-4 rounded-md" />
                </div>
                <Skeleton className="w-full h-2 rounded-full" />
              </div>
            ))}
          </div>
        </SkeletonCard>
      </div>
    </div>
  );
}

/** Full page generic skeleton */
export function PageSkeleton({ titleWidth = 120 }: { titleWidth?: number }) {
  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <Skeleton className="h-7 rounded-md" style={{ width: titleWidth }} />
          <Skeleton className="w-56 h-3 rounded-md" />
        </div>
        <Skeleton className="w-24 h-9 rounded-lg" />
      </div>
      <TableSkeleton rows={6} columns={4} />
    </div>
  );
}

/** Inline loading spinner for buttons */
export function ButtonSpinner({ className }: { className?: string }) {
  return (
    <svg
      className={cn("animate-spin h-4 w-4 text-current", className)}
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  );
}

/** Shimmer wrapper for enhanced skeleton effect */
export function Shimmer({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("relative overflow-hidden", className)}>
      {children}
      <div
        className="absolute inset-0 -translate-x-full animate-shimmer"
        style={{
          background:
            "linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.4) 50%, transparent 100%)",
        }}
      />
    </div>
  );
}
