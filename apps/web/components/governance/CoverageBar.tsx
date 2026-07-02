import { cn } from "@/lib/utils";

/** Horizontal coverage bar coloured by how complete the coverage is. */
export function CoverageBar({ pct, className }: { pct: number; className?: string }) {
  const tone = pct >= 80 ? "bg-success" : pct >= 40 ? "bg-warning" : "bg-danger";
  return (
    <div className={cn("h-1.5 w-full overflow-hidden rounded-full bg-white/[0.06]", className)}>
      <div
        className={cn("h-full rounded-full transition-all duration-300", tone)}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
