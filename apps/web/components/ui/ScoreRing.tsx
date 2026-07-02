import { cn } from "@/lib/utils";

type Tone = "accent" | "success" | "warning" | "danger";

const strokeMap: Record<Tone, string> = {
  accent: "var(--accent)",
  success: "var(--success)",
  warning: "var(--warning)",
  danger: "var(--danger)",
};

interface ScoreRingProps {
  /** 0–100 fill percentage. */
  value: number;
  /** Large number rendered in the center (defaults to value). */
  display?: string;
  /** Small caption under the center number. */
  caption?: string;
  tone?: Tone;
  size?: number;
  className?: string;
}

/**
 * A static SVG radial gauge. No animation library, no client JS — renders
 * identically on the server.
 */
export function ScoreRing({
  value,
  display,
  caption,
  tone = "accent",
  size = 132,
  className,
}: ScoreRingProps) {
  const stroke = 9;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(100, value));
  const offset = circumference - (clamped / 100) * circumference;
  const center = size / 2;

  return (
    <div
      className={cn("relative inline-flex items-center justify-center", className)}
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke="var(--border)"
          strokeWidth={stroke}
        />
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke={strokeMap[tone]}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-mono text-3xl font-medium tabular-nums tracking-tight text-foreground">
          {display ?? clamped}
        </span>
        {caption && (
          <span className="mt-0.5 text-2xs font-medium uppercase tracking-wider text-foreground-muted">
            {caption}
          </span>
        )}
      </div>
    </div>
  );
}
