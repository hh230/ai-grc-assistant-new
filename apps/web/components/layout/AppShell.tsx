"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { usePathname } from "@/i18n/navigation";
import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";
import { CommandPalette } from "@/components/search/CommandPalette";
import { useFocusTrap } from "@/lib/hooks/useFocusTrap";
import { cn } from "@/lib/utils";

interface AppShellProps {
  children: ReactNode;
}

/**
 * The workspace frame: a persistent left navigation, a top bar, and a scrolling
 * content well. Mounted once in the root layout so the shell does not remount
 * between routes. Below `lg` the sidebar collapses into an overlay drawer.
 */
export function AppShell({ children }: AppShellProps) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const pathname = usePathname();
  const drawerRef = useRef<HTMLDivElement>(null);
  useFocusTrap(drawerRef, mobileNavOpen, () => setMobileNavOpen(false));

  // Close the drawer whenever the route changes (covers nav clicks and back/forward).
  useEffect(() => {
    setMobileNavOpen(false);
  }, [pathname]);

  // ⌘K / Ctrl+K opens the global command palette from anywhere in the workspace.
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setSearchOpen(true);
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

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
        <Topbar onMenuClick={() => setMobileNavOpen(true)} onSearchClick={() => setSearchOpen(true)} />
        <main className="scrollbar-thin flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-[1320px] px-4 py-7 sm:px-6">{children}</div>
        </main>
      </div>

      <CommandPalette open={searchOpen} onClose={() => setSearchOpen(false)} />
    </div>
  );
}
