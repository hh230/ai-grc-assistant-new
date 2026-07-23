// The data hook for the Result page. React never fetches directly — the client does; the hook holds
// the load/error state. (No polling: a Result exists only for a completed mission, so it is static.)

import { useEffect, useMemo, useState } from "react";

import { ApiError, MissionApiClient, type ResultView } from "../api/client";

export type ResultState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; result: ResultView };

export function useResult(missionId: string): { client: MissionApiClient; state: ResultState } {
  const client = useMemo(() => new MissionApiClient(), []);
  const [state, setState] = useState<ResultState>({ kind: "loading" });

  useEffect(() => {
    let live = true;
    setState({ kind: "loading" });
    client
      .getResult(missionId)
      .then((result) => live && setState({ kind: "ready", result }))
      .catch((e: unknown) => {
        const message = e instanceof ApiError ? e.message : String(e);
        if (live) setState({ kind: "error", message });
      });
    return () => {
      live = false;
    };
  }, [client, missionId]);

  return { client, state };
}
