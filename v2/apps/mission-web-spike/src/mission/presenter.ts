// The Mission Detail Presenter / ViewModel (owner's rule: the layer between the View and the REST
// client). React never sees the client; it sees this. Everything that would otherwise pile up inside
// components lives here — the load/error state machine, polling while the mission is active, the
// permission (`canApprove`), and mapping API errors to a message. Framework-agnostic (no React), so
// it is unit-testable and the View stays declarative.

import {
  ApiError,
  type CurrentUser,
  type MissionApiClient,
  type MissionDetail,
} from "../api/client";

export type DetailState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; detail: MissionDetail };

// The mission is still moving (worth polling) in these states.
const ACTIVE = new Set(["created", "planned", "executing", "resumed"]);
const POLL_MS = 1500;

type Listener = (state: DetailState) => void;

export class MissionDetailPresenter {
  private state: DetailState = { kind: "loading" };
  private readonly listeners = new Set<Listener>();
  private timer: ReturnType<typeof setTimeout> | undefined;
  private stopped = false;

  constructor(
    private readonly client: MissionApiClient,
    private readonly missionId: string,
    private readonly user: CurrentUser,
  ) {}

  getState(): DetailState {
    return this.state;
  }

  get canApprove(): boolean {
    return this.user.roles.includes("approver");
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  async start(): Promise<void> {
    // Re-enable after any prior stop() — React StrictMode mounts, cleans up, then mounts again on
    // the same (memoized) presenter, so a permanent stop would block the second run's updates.
    this.stopped = false;
    await this.refresh();
    this.scheduleMaybe();
  }

  stop(): void {
    this.stopped = true;
    if (this.timer !== undefined) clearTimeout(this.timer);
  }

  async approve(stepId: string, comment = ""): Promise<void> {
    await this.client.approve(this.missionId, stepId, comment);
    await this.refresh();
  }

  async reject(stepId: string, comment = ""): Promise<void> {
    await this.client.reject(this.missionId, stepId, comment);
    await this.refresh();
  }

  private set(state: DetailState): void {
    this.state = state;
    for (const listener of this.listeners) listener(state);
  }

  private async refresh(): Promise<void> {
    try {
      const detail = await this.client.getMissionDetail(this.missionId);
      if (!this.stopped) this.set({ kind: "ready", detail });
    } catch (error) {
      const message = error instanceof ApiError ? error.message : String(error);
      if (!this.stopped) this.set({ kind: "error", message });
    }
  }

  // Poll only while the mission is active — never a blocking wait (Interaction Principle 10). No
  // websocket/SSE (the API is poll-based); when execution moves async, this is the only change.
  private scheduleMaybe(): void {
    if (this.stopped || this.state.kind !== "ready") return;
    if (!ACTIVE.has(this.state.detail.status)) return;
    this.timer = setTimeout(async () => {
      await this.refresh();
      this.scheduleMaybe();
    }, POLL_MS);
  }
}
