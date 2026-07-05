"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

interface PopoverProps {
  /** Render-prop trigger; receives `open` so the trigger can reflect state. */
  trigger: (open: boolean) => ReactNode;
  children: ReactNode;
  align?: "start" | "end";
  /** Width of the panel in pixels. */
  width?: number;
  panelClassName?: string;
  /**
   * Accessible name for the trigger button. Required whenever the visible trigger
   * content is icon-only or a short avatar/initials fragment that wouldn't make sense
   * read aloud on its own (e.g. "JD" or a bell icon) — screen readers announce this
   * instead of the trigger's visible text.
   */
  ariaLabel?: string;
  /**
   * Controlled open state — pass this + `onOpenChange` when a caller needs to close the
   * panel programmatically (e.g. before opening a Modal that a menu item triggers, so the
   * panel doesn't stay open behind/beside the dialog). Omit both for the default
   * uncontrolled behavior (click-to-toggle, outside-click/Escape to close).
   */
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

/**
 * Lightweight popover: opens on click, closes on outside-click or Escape.
 * The panel uses a fully solid background (no transparency) so overlaid text stays
 * readable regardless of what's behind it — every dropdown/menu in the app renders
 * through this one component, so fixing it here fixes all of them.
 */
export function Popover({
  trigger,
  children,
  align = "end",
  width = 288,
  panelClassName,
  ariaLabel,
  open: controlledOpen,
  onOpenChange,
}: PopoverProps) {
  const [internalOpen, setInternalOpen] = useState(false);
  const isControlled = controlledOpen !== undefined;
  const open = isControlled ? controlledOpen : internalOpen;
  const rootRef = useRef<HTMLDivElement>(null);

  const setOpen = useCallback(
    (value: boolean) => {
      if (!isControlled) setInternalOpen(value);
      onOpenChange?.(value);
    },
    [isControlled, onOpenChange],
  );

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
  }, [open, setOpen]);

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={ariaLabel}
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
            "bg-surface-elevated shadow-elevated",
            "origin-top",
            align === "end" ? "end-0" : "start-0",
            panelClassName,
          )}
        >
          {children}
        </div>
      )}
    </div>
  );
}
