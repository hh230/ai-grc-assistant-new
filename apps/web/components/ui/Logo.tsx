import Image from "next/image";
import { cn } from "@/lib/utils";

/** Intrinsic ratio of /public/brand/logo.svg (2811 × 2548). */
const LOGO_ASPECT_RATIO = 2811 / 2548;

interface LogoMarkProps {
  /** Rendered height in pixels; width is derived from the logo's own aspect ratio. */
  size?: number;
  className?: string;
  priority?: boolean;
}

/** The brand mark on its own — used wherever only the icon (no wordmark) fits. */
export function LogoMark({ size = 32, className, priority }: LogoMarkProps) {
  return (
    <Image
      src="/brand/logo.svg"
      alt="Rasheed"
      width={Math.round(size * LOGO_ASPECT_RATIO)}
      height={size}
      className={cn("shrink-0", className)}
      priority={priority}
    />
  );
}

interface LogoProps extends LogoMarkProps {
  wordmark?: string;
  tagline?: string;
  /** Overrides the default text-xl/font-bold wordmark styling (e.g. footer wants text-sm/font-semibold). */
  wordmarkClassName?: string;
}

/** Brand mark + optional wordmark/tagline, laid out the way the sidebar and marketing nav need it. */
export function Logo({ size = 32, wordmark, tagline, wordmarkClassName, className, priority }: LogoProps) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <LogoMark size={size} priority={priority} />
      {wordmark ? (
        <span className="leading-tight">
          <span className={cn("block tracking-tight text-foreground", wordmarkClassName ?? "text-xl font-bold")}>
            {wordmark}
          </span>
          {tagline ? <span className="block text-2xs text-foreground-muted">{tagline}</span> : null}
        </span>
      ) : null}
    </span>
  );
}
