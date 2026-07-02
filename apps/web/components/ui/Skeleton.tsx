import { cn } from "@/lib/utils";

/**
 * Skeleton placeholder for known-shape content (design proposal §16) — used instead of a
 * spinner wherever the loaded content's dimensions are predictable, so there's no layout
 * shift once it resolves. A slow, low-opacity shimmer; never a bounce or pulse.
 */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn("animate-skeleton-shimmer rounded-md bg-surface-elevated", className)}
      aria-hidden
    />
  );
}
