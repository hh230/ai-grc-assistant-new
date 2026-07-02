"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

interface PopoverProps {
  /** Render-prop trigger; receives `open` so the trigger can reflect state. */
  trigger: (open: boolean) => ReactNode;
  children: ReactNode;
  align?: "start" | "end";
  /** Width of the panel in pixels. */
  width?: number;
  panelClassName?: string;
}

/**
 * Lightweight popover: opens on click, closes on outside-click or Escape.
 * Glassmorphism is applied here (a floating overlay) where it is appropriate —
 * not on the underlying content cards.
 */
export function Popover({
  trigger,
  children,
  align = "end",
  width = 288,
  panelClassName,
}: PopoverProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="block rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-accent/40"
      >
        {trigger(open)}
      </button>
      {open && (
        <div
          role="menu"
          style={{ width }}
          className={cn(
            "absolute z-50 mt-2 overflow-hidden rounded-xl border border-hairline-strong",
            "bg-surface-2/85 backdrop-blur-xl shadow-elevated",
            "origin-top",
            align === "end" ? "right-0" : "left-0",
            panelClassName,
          )}
        >
          {children}
        </div>
      )}
    </div>
  );
}
