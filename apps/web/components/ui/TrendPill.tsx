import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Trend } from "@/lib/data";

interface TrendPillProps {
  trend: Trend;
  value: number;
  /** Which direction is "good". Compliance improves up; risk improves down. */
  goodWhen?: "up" | "down";
  suffix?: string;
  className?: string;
}

export function TrendPill({
  trend,
  value,
  goodWhen = "up",
  suffix = "%",
  className,
}: TrendPillProps) {
  const Icon = trend === "up" ? ArrowUpRight : trend === "down" ? ArrowDownRight : Minus;
  const isGood = trend === "flat" ? null : trend === goodWhen;
  const tone = isGood === null ? "text-foreground-muted" : isGood ? "text-success" : "text-danger";

  return (
    <span
      className={cn(
        "inline-flex items-center gap-0.5 text-xs font-medium tabular-nums",
        tone,
        className,
      )}
    >
      <Icon className="h-3.5 w-3.5" strokeWidth={2} />
      {value > 0 ? value.toFixed(1) : "—"}
      {value > 0 ? suffix : ""}
    </span>
  );
}
