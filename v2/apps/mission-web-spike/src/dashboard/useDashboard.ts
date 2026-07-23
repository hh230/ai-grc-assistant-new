// The thin React bridge for the Dashboard. React never calls fetch — the client does; this hook only
// owns the load/error state and a reload trigger. (The Dashboard has no polling or permissions, so it
// needs no Presenter class — the "presentation" is the read model, mapped straight in the View.)

import { useEffect, useMemo, useState } from "react";

import { type DashboardData, MissionApiClient } from "../api/client";

export type DashboardLoad =
  | { state: "loading" }
  | { state: "error"; message: string }
  | { state: "ready"; data: DashboardData };

export function useDashboard(): { load: DashboardLoad; reload: () => void } {
  const client = useMemo(() => new MissionApiClient(), []);
  const [reloadKey, setReloadKey] = useState(0);
  const [load, setLoad] = useState<DashboardLoad>({ state: "loading" });

  useEffect(() => {
    let live = true;
    setLoad({ state: "loading" });
    client
      .getDashboard()
      .then((data) => live && setLoad({ state: "ready", data }))
      .catch((e: unknown) => {
        const message = e instanceof Error ? e.message : String(e);
        if (live) setLoad({ state: "error", message });
      });
    return () => {
      live = false;
    };
  }, [client, reloadKey]);

  return { load, reload: () => setReloadKey((k) => k + 1) };
}
