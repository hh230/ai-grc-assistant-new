import Image from "next/image";
import { cn } from "@/lib/utils";

interface ProductScreenshotProps {
  src: string;
  alt: string;
  caption: string;
  url?: string;
  width: number;
  height: number;
  className?: string;
}

/**
 * Framed real-product screenshot (V2-P3 design proposal §7) — never an illustration.
 * The browser-chrome bar is intentionally muted (no red/yellow/green traffic lights):
 * a real device frame, not a decorative flourish (Product Personality, proposal §1).
 */
export function ProductScreenshot({
  src,
  alt,
  caption,
  url = "app.rasheed.sa",
  width,
  height,
  className,
}: ProductScreenshotProps) {
  return (
    <figure className={cn(className)}>
      <div className="overflow-hidden rounded-2xl border border-hairline bg-surface shadow-elevated">
        <div className="flex items-center gap-3 border-b border-hairline bg-surface-2 px-4 py-2.5">
          <div className="flex gap-1.5" aria-hidden>
            <span className="h-2.5 w-2.5 rounded-full bg-foreground-muted/25" />
            <span className="h-2.5 w-2.5 rounded-full bg-foreground-muted/25" />
            <span className="h-2.5 w-2.5 rounded-full bg-foreground-muted/25" />
          </div>
          <span className="mx-auto flex items-center gap-1.5 rounded-md bg-surface px-3 py-1 text-2xs text-foreground-muted">
            {url}
          </span>
        </div>
        <Image
          src={src}
          alt={alt}
          width={width}
          height={height}
          className="w-full"
          sizes="(min-width: 1024px) 720px, 100vw"
        />
      </div>
      <figcaption className="mt-3 text-center text-xs text-foreground-muted">{caption}</figcaption>
    </figure>
  );
}
