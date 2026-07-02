"use client";

import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { LOGIN_PATH } from "@/lib/auth/config";
import { can, type Action, type ResourceType } from "@/lib/auth/permissions";
import type { UserRole } from "@/lib/auth/roles";
import type { SessionUser } from "@/lib/auth/types";

interface SessionContextValue {
  user: SessionUser;
  /** True when the user holds at least one of the given roles. */
  hasRole: (...roles: UserRole[]) => boolean;
  /** True when the user may perform `action` on `resource` (mirrors backend RBAC). */
  can: (action: Action, resource: ResourceType) => boolean;
  signOut: () => Promise<void>;
  isSigningOut: boolean;
}

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ user, children }: { user: SessionUser; children: ReactNode }) {
  const router = useRouter();
  const [isSigningOut, setIsSigningOut] = useState(false);

  const signOut = useCallback(async () => {
    setIsSigningOut(true);
    try {
      await fetch("/api/auth/logout", { method: "POST" });
      // Full navigation so middleware re-evaluates and all client state is dropped.
      window.location.assign(LOGIN_PATH);
    } catch {
      setIsSigningOut(false);
      router.push(LOGIN_PATH);
    }
  }, [router]);

  const hasRole = useCallback(
    (...roles: UserRole[]) => roles.some((r) => user.roles.includes(r)),
    [user.roles],
  );
  const canDo = useCallback(
    (action: Action, resource: ResourceType) => can(user.roles, action, resource),
    [user.roles],
  );

  return (
    <SessionContext.Provider value={{ user, hasRole, can: canDo, signOut, isSigningOut }}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSession(): SessionContextValue {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error("useSession must be used within a SessionProvider");
  }
  return context;
}
