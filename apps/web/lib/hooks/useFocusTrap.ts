"use client";

import { useEffect, useRef, type RefObject } from "react";

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Shared focus-trap behavior for overlays (Modal, the mobile nav drawer, the command
 * palette): while `active`, moves focus into the container, keeps Tab cycling inside it,
 * calls `onEscape` on Escape, and restores focus to whatever was focused before opening.
 *
 * Callers must not also set a native `autoFocus` on a descendant: `autoFocus` runs during
 * React's commit phase, before this effect (a passive effect) ever sees `document
 * .activeElement` — by the time the effect runs, focus would already be inside the
 * container, so the *real* trigger (whatever had focus before the overlay opened) could
 * never be captured. Letting this effect be the only thing that moves focus in avoids that.
 */
export function useFocusTrap(
  containerRef: RefObject<HTMLElement | null>,
  active: boolean,
  onEscape: () => void,
) {
  const triggerRef = useRef<Element | null>(null);

  useEffect(() => {
    if (!active) return;
    const container = containerRef.current;
    // Guards against React StrictMode's dev-only double-invoke (mount → cleanup → mount):
    // the second mount would otherwise see focus already inside the container (moved there
    // by the first mount) and overwrite the real trigger with an element from inside the
    // overlay itself.
    if (!container?.contains(document.activeElement)) {
      triggerRef.current = document.activeElement;
    }
    const focusable = container?.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
    (focusable?.[0] ?? container)?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onEscape();
        return;
      }
      if (event.key !== "Tab" || !container) return;
      const nodes = container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      if (!first || !last) return;
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      if (triggerRef.current instanceof HTMLElement) triggerRef.current.focus();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active]);
}
