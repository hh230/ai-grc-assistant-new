import { cn } from "@/lib/utils";

type Tone = "accent" | "success" | "warning" | "danger";

const fillMap: Record<Tone, string> = {
  accent: "bg-accent",
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
};

interface ProgressBarProps {
  value: number;
  target?: number;
  tone?: Tone;
  className?: string;
}

export function ProgressBar({ value, target, tone = "accent", className }: ProgressBarProps) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div
      className={cn(
        "relative h-1.5 w-full overflow-hidden rounded-full bg-surface-elevated",
        className,
      )}
    >
      <div
        className={cn(
          "h-full rounded-full transition-[width] duration-700 ease-out-soft",
          fillMap[tone],
        )}
        style={{ width: `${clamped}%` }}
      />
      {typeof target === "number" && (
        <span
          aria-hidden
          className="absolute top-1/2 h-3 w-px -translate-y-1/2 bg-hairline-strong"
          style={{ left: `${Math.max(0, Math.min(100, target))}%` }}
        />
      )}
    </div>
  );
}
