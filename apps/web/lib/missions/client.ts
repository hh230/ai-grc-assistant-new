/** Browser-side Missions API client — calls this app's own `/api/missions` route. */

import type { Mission } from "./types";

async function parseError(response: Response): Promise<string> {
  const data = (await response.json().catch(() => ({}))) as { error?: string };
  return data.error ?? `Request failed (${response.status}).`;
}

export async function fetchMissions(): Promise<Mission[]> {
  const response = await fetch("/api/missions", { cache: "no-store" });
  if (!response.ok) throw new Error(await parseError(response));
  return ((await response.json()) as { missions: Mission[] }).missions;
}
