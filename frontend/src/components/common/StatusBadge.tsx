import { cn } from "@/lib/utils";

interface StatusBadgeProps {
  isConnected: boolean;
  className?: string;
}

export function StatusBadge({ isConnected, className }: StatusBadgeProps) {
  return (
    <div
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border transition",
        isConnected
          ? "bg-emerald-50 border-emerald-300 text-emerald-700"
          : "bg-amber-50 border-amber-300 text-amber-700",
        className
      )}
      role="status"
    >
      <span
        className={cn(
          "w-2 h-2 rounded-full",
          isConnected ? "bg-emerald-500 animate-pulse" : "bg-amber-500"
        )}
      />
      <span>{isConnected ? "TERHUBUNG" : "TERPUTUS"}</span>
    </div>
  );
}
