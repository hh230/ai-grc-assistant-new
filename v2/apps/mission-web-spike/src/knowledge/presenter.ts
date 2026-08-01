// The Knowledge Presenter / ViewModel (owner's rule: the layer between the View and the REST client).
// React never sees the client; it sees this. It owns the load/error state machine, grouping the flat
// document list into Evidence Collections, polling while any document is still ingesting, and the
// upload action. Framework-agnostic (no React), so it is unit-testable and the View stays declarative.

import { ApiError, type DocumentItem, type MissionApiClient } from "../api/client";
import { toCollections, type EvidenceCollectionVM } from "./collections";

export type KnowledgeState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; collections: EvidenceCollectionVM[]; total: number };

const POLL_MS = 1500;

type Listener = (state: KnowledgeState) => void;

export class KnowledgePresenter {
  private state: KnowledgeState = { kind: "loading" };
  private readonly listeners = new Set<Listener>();
  private timer: ReturnType<typeof setTimeout> | undefined;
  private stopped = false;

  constructor(private readonly client: MissionApiClient) {}

  getState(): KnowledgeState {
    return this.state;
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  async start(): Promise<void> {
    // Re-enable after any prior stop() — StrictMode mounts, cleans up, then mounts again on the same
    // memoized presenter, so a permanent stop would block the second run's updates.
    this.stopped = false;
    await this.refresh();
    this.scheduleMaybe();
  }

  stop(): void {
    this.stopped = true;
    if (this.timer !== undefined) clearTimeout(this.timer);
  }

  // Upload a document, then refresh so it appears (as "ingesting" then, on the next poll, "ready").
  // Throws on failure so the View can show an inline upload error without losing the current list.
  async upload(evidenceKind: string, file: File): Promise<void> {
    await this.client.uploadDocument(evidenceKind, file);
    await this.refresh();
    this.scheduleMaybe();
  }

  private set(state: KnowledgeState): void {
    this.state = state;
    for (const listener of this.listeners) listener(state);
  }

  private async refresh(): Promise<void> {
    try {
      const res = await this.client.listDocuments();
      if (!this.stopped) {
        this.set({ kind: "ready", collections: toCollections(res.items), total: res.items.length });
      }
    } catch (error) {
      const message = error instanceof ApiError ? error.message : String(error);
      if (!this.stopped) this.set({ kind: "error", message });
    }
  }

  // Poll only while something is still ingesting — never a blocking wait. When nothing is ingesting,
  // the list is settled and polling stops (Interaction Principle 10).
  private scheduleMaybe(): void {
    if (this.stopped || this.state.kind !== "ready") return;
    if (!this.hasIngesting(this.state)) return;
    this.timer = setTimeout(async () => {
      await this.refresh();
      this.scheduleMaybe();
    }, POLL_MS);
  }

  private hasIngesting(state: { collections: EvidenceCollectionVM[] }): boolean {
    return state.collections.some((collection) =>
      collection.documents.some((doc: DocumentItem) => doc.status === "ingesting"),
    );
  }
}
