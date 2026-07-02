"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { usePathname } from "@/i18n/navigation";
import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";
import { cn } from "@/lib/utils";

interface AppShellProps {
  children: ReactNode;
}

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * The workspace frame: a persistent left navigation, a top bar, and a scrolling
 * content well. Mounted once in the root layout so the shell does not remount
 * between routes. Below `lg` the sidebar collapses into an overlay drawer.
 */
export function AppShell({ children }: AppShellProps) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const pathname = usePathname();
  const drawerRef = useRef<HTMLDivElement>(null);
  const menuTriggerRef = useRef<Element | null>(null);

  // Close the drawer whenever the route changes (covers nav clicks and back/forward).
  useEffect(() => {
    setMobileNavOpen(false);
  }, [pathname]);

  // While the drawer is open: move focus into it, trap Tab, allow Escape to dismiss,
  // and restore focus to whatever opened it on close (same pattern as `Modal`).
  useEffect(() => {
    if (!mobileNavOpen) return;
    menuTriggerRef.current = document.activeElement;
    const drawer = drawerRef.current;
    const focusable = drawer?.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
    focusable?.[0]?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setMobileNavOpen(false);
        return;
      }
      if (event.key !== "Tab" || !drawer) return;
      const nodes = drawer.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
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
      if (menuTriggerRef.current instanceof HTMLElement) menuTriggerRef.current.focus();
    };
  }, [mobileNavOpen]);

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Desktop navigation — always present at lg and above */}
      <div className="hidden lg:block">
        <Sidebar />
      </div>

      {/* Mobile navigation — overlay drawer below lg */}
      <div
        className={cn("fixed inset-0 z-50 lg:hidden", mobileNavOpen ? "" : "pointer-events-none")}
        aria-hidden={!mobileNavOpen}
      >
        <div
          onClick={() => setMobileNavOpen(false)}
          className={cn(
            "absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity duration-300",
            mobileNavOpen ? "opacity-100" : "opacity-0",
          )}
        />
        <div
          ref={drawerRef}
          role="dialog"
          aria-modal="true"
          className={cn(
            "absolute inset-y-0 start-0 shadow-elevated transition-transform duration-300 ease-out-soft",
            // Slides in from the "start" edge (left in LTR, right in RTL) — `start-0`
            // handles the resting position, but Tailwind has no logical translate utility,
            // so the off-screen direction needs an explicit `rtl:` override.
            mobileNavOpen ? "translate-x-0" : "-translate-x-full rtl:translate-x-full",
          )}
        >
          <Sidebar onNavigate={() => setMobileNavOpen(false)} />
        </div>
      </div>

      <div className="flex min-w-0 flex-1 flex-col" aria-hidden={mobileNavOpen || undefined}>
        <Topbar onMenuClick={() => setMobileNavOpen(true)} />
        <main className="scrollbar-thin flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-[1320px] px-4 py-7 sm:px-6">{children}</div>
        </main>
      </div>
    </div>
  );
}
