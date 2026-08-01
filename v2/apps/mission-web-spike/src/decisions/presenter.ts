// The Decisions Presenter / ViewModel (owner's rule: the layer between the View and the REST client).
// React never sees the client; it sees this. It owns the load/error state, the permission to decide
// (`canDecide` = the Approver role), and Approve/Reject — which call the REUSED S2 command and then
// refresh so a decided item leaves the list. Framework-agnostic (no React), so it is unit-testable.

import {
  ApiError,
  type CurrentUser,
  type DecisionItem,
  type MissionApiClient,
  type RecentDecision,
} from "../api/client";

// #7 — after a decision, the mission's story must not go silent. We capture which mission was decided
// so the view can report the *effect* of the decision in human terms ("the mission has resumed") —
// what the user was waiting to learn after clicking Approve, not the raw current status.
export interface DecisionOutcome {
  decided: "approved" | "rejected";
  missionType: string;
  missionScope: string;
}

export type DecisionsState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | {
      kind: "ready";
      items: DecisionItem[];
      recent: RecentDecision[];
      outcome: DecisionOutcome | null;
    };

type Listener = (state: DecisionsState) => void;

export class DecisionsPresenter {
  private state: DecisionsState = { kind: "loading" };
  private readonly listeners = new Set<Listener>();
  private stopped = false;
  private lastOutcome: DecisionOutcome | null = null;

  constructor(
    private readonly client: MissionApiClient,
    private readonly user: CurrentUser,
  ) {}

  getState(): DecisionsState {
    return this.state;
  }

  get canDecide(): boolean {
    return this.user.roles.includes("approver");
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  async start(): Promise<void> {
    this.stopped = false;
    await this.refresh();
  }

  stop(): void {
    this.stopped = true;
  }

  // Approve / Reject reuse the S2 command; `decision_id` is the {step_id} it takes. On success the
  // mission resumes, so a refresh drops the item from the list — the page's one question stays true.
  // We note which mission was decided (#7) so the view can report the decision's effect in human terms.
  async approve(missionId: string, decisionId: string): Promise<void> {
    const item = this.currentItem(missionId);
    await this.client.approve(missionId, decisionId);
    this.recordOutcome("approved", item);
    await this.refresh();
  }

  async reject(missionId: string, decisionId: string): Promise<void> {
    const item = this.currentItem(missionId);
    await this.client.reject(missionId, decisionId);
    this.recordOutcome("rejected", item);
    await this.refresh();
  }

  reload(): void {
    void this.refresh();
  }

  private currentItem(missionId: string): DecisionItem | undefined {
    return this.state.kind === "ready"
      ? this.state.items.find((i) => i.mission_id === missionId)
      : undefined;
  }

  private recordOutcome(decided: "approved" | "rejected", item: DecisionItem | undefined): void {
    this.lastOutcome = item
      ? { decided, missionType: item.mission_type, missionScope: item.mission_scope }
      : null;
  }

  private set(state: DecisionsState): void {
    this.state = state;
    for (const listener of this.listeners) listener(state);
  }

  private async refresh(): Promise<void> {
    try {
      // Fetch the waiting queue and the recent history together — the view shows the queue, and
      // falls back to recent decisions when nothing is waiting (so the page stays alive).
      const [waiting, recent] = await Promise.all([
        this.client.listDecisions(),
        this.client.listRecentDecisions(),
      ]);
      if (!this.stopped)
        this.set({
          kind: "ready",
          items: waiting.items,
          recent: recent.items,
          outcome: this.lastOutcome,
        });
    } catch (error) {
      const message = error instanceof ApiError ? error.message : String(error);
      if (!this.stopped) this.set({ kind: "error", message });
    }
  }
}
