// The REST client — the ONLY place that calls `fetch` and knows the API contract shapes (owner's
// rule: React never fetches directly; the ViewModel/Presenter sits between the View and this client).
// These types mirror the grc-api representations exactly and go no deeper (no aggregate, DB row, ORM).

export interface MissionListItem {
  id: string;
  type: string;
  scope: string;
  status: string;
  created_at: number;
  updated_at: number;
}

export interface MissionListResponse {
  items: MissionListItem[];
  page: number;
  page_size: number;
  total: number;
  has_next: boolean;
}

export interface MissionQuery {
  status?: string;
  type?: string;
  q?: string;
  page?: number;
  page_size?: number;
}

export interface PlanStep {
  id: string;
  description: string;
}

export interface Finding {
  step_id: string;
  title: string;
  summary: string;
  citations: string[];
  confidence: number | null;
}

export interface Approval {
  id: string;
  proposed_action: string;
  status: string; // "pending" | "approved" | "rejected"
}

export interface MissionDetail {
  id: string;
  type: string;
  scope: string;
  status: string;
  plan: PlanStep[];
  findings: Finding[];
  approval: Approval | null;
  created_at: number;
  updated_at: number;
}

export interface CommandResult {
  mission_id: string;
  status: string;
  approval_pending: boolean;
}

// The Mission Created review-station payload: the mission + a plan summary (steps · approvals).
export interface MissionCreated {
  mission: MissionDetail;
  steps: number;
  human_approvals: number;
}

// --- Result (the domain's "Deliverable"; the user sees "Result") ---
export interface ResultSection {
  heading: string;
  body: string;
  citations: string[];
  confidence: number | null;
}

export interface GapRow {
  control_code: string;
  control_title: string;
  covered: boolean;
  evidence: string[];
}

export interface Coverage {
  framework: string;
  coverage: number;
  covered_count: number;
  total: number;
  gaps: GapRow[];
}

export interface TrustBarData {
  evidence_count: number;
  human_review: string;
  updated_at: number;
}

// Polymorphic content, discriminated by `kind` (the page never switches on it — a presenter does).
export interface GenericResultContent {
  kind: "generic";
  sections: ResultSection[];
}

export interface GapResultContent {
  kind: "gap_assessment";
  sections: ResultSection[];
  coverage: Coverage;
}

export type ResultContent = GenericResultContent | GapResultContent;

export interface ResultView {
  mission_id: string;
  title: string;
  trust: TrustBarData;
  content: ResultContent;
}

// --- Decisions ("What decisions are waiting for me?") ---
// One waiting decision (grc-api §4 Approvals queue item). The unit is a decision; the mission is
// context. `decision_id` is what Approve/Reject acts on (passed as the {step_id} the command takes).
export interface DecisionItem {
  mission_id: string;
  decision_id: string;
  proposed_action: string;
  mission_type: string;
  mission_scope: string;
  waiting_since: number;
  evidence_count: number;
}

export interface DecisionsResponse {
  items: DecisionItem[];
}

// A decision already made — shown when nothing is waiting, so the page stays alive.
export interface RecentDecision {
  proposed_action: string;
  approved: boolean;
  decided_at: number;
}

export interface RecentDecisionsResponse {
  items: RecentDecision[];
}

// --- Dashboard ("What needs my attention right now?") ---
export interface RecentMission {
  id: string;
  type: string;
  scope: string;
  completed_at: number;
}

export interface CoverageSnapshot {
  percent: number; // 0..1 — a point-in-time snapshot, not a compliance score
  covered: number;
  total: number;
  assessments: number;
}

export interface DashboardData {
  waiting: number;
  running: number;
  failed: number;
  recent: RecentMission[];
  coverage: CoverageSnapshot | null; // null until a Gap Assessment has completed
}

// --- Knowledge (the tenant's Evidence) ---
// One document as the Knowledge view lists it (grc-api §2 `Document`). `evidence_kind` is the
// Evidence Collection it belongs to; `status` is its ingestion state. No chunk/embedding detail.
export interface DocumentItem {
  id: string;
  filename: string;
  evidence_kind: string;
  status: string; // "ingesting" | "ready" | "failed"
  uploaded_at: number;
  size: number;
}

export interface DocumentListResponse {
  items: DocumentItem[];
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

// The current user is opaque to React — the client uses the credential for auth; the Presenter uses
// the roles for permissions. A real app gets this from the session; the spike uses a seeded dev user
// (an Approver, so the gate card's Approve/Reject show).
export interface CurrentUser {
  credential: string;
  roles: string[];
}

export const CURRENT_USER: CurrentUser = {
  credential: "dev-approver-a",
  roles: ["practitioner", "approver"],
};

export class MissionApiClient {
  constructor(private readonly user: CurrentUser = CURRENT_USER) {}

  private headers(): Record<string, string> {
    return {
      Authorization: `Bearer ${this.user.credential}`,
      "Content-Type": "application/json",
    };
  }

  private async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const res = await fetch(path, {
      method,
      headers: this.headers(),
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!res.ok) {
      const parsed = (await res.json().catch(() => null)) as { error?: { code?: string; message?: string } } | null;
      throw new ApiError(res.status, parsed?.error?.code ?? "error", parsed?.error?.message ?? `request failed (${res.status})`);
    }
    return (await res.json()) as T;
  }

  listMissions(query: MissionQuery = {}): Promise<MissionListResponse> {
    const params = new URLSearchParams();
    if (query.status) params.set("status", query.status);
    if (query.type) params.set("type", query.type);
    if (query.q) params.set("q", query.q);
    if (query.page) params.set("page", String(query.page));
    if (query.page_size) params.set("page_size", String(query.page_size));
    const qs = params.toString();
    return this.request<MissionListResponse>("GET", `/v1/missions${qs ? `?${qs}` : ""}`);
  }

  getMissionDetail(id: string): Promise<MissionDetail> {
    return this.request<MissionDetail>("GET", `/v1/missions/${id}`);
  }

  // Create returns the mission + its plan (for the review station). An Idempotency-Key makes a
  // double-submit safe (the same click never creates two missions).
  async createMission(input: { type: string; scope: string; documentIds?: string[] }): Promise<MissionCreated> {
    const res = await fetch("/v1/missions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${this.user.credential}`,
        "Content-Type": "application/json",
        "Idempotency-Key": crypto.randomUUID(),
      },
      body: JSON.stringify({ type: input.type, scope: input.scope, document_ids: input.documentIds ?? [] }),
    });
    if (!res.ok) {
      const parsed = (await res.json().catch(() => null)) as { error?: { code?: string; message?: string } } | null;
      throw new ApiError(res.status, parsed?.error?.code ?? "error", parsed?.error?.message ?? `create failed (${res.status})`);
    }
    return (await res.json()) as MissionCreated;
  }

  // "Start mission" — the /run path is the contract detail; the product word is Start.
  startMission(id: string): Promise<CommandResult> {
    return this.request<CommandResult>("POST", `/v1/missions/${id}/run`);
  }

  approve(id: string, stepId: string, comment = ""): Promise<CommandResult> {
    return this.request<CommandResult>("POST", `/v1/missions/${id}/approvals/${stepId}/approve`, { comment });
  }

  reject(id: string, stepId: string, comment = ""): Promise<CommandResult> {
    return this.request<CommandResult>("POST", `/v1/missions/${id}/approvals/${stepId}/reject`, { comment });
  }

  getResult(id: string): Promise<ResultView> {
    return this.request<ResultView>("GET", `/v1/missions/${id}/deliverable`);
  }

  getDashboard(): Promise<DashboardData> {
    return this.request<DashboardData>("GET", "/v1/dashboard");
  }

  listDecisions(): Promise<DecisionsResponse> {
    return this.request<DecisionsResponse>("GET", "/v1/approvals?status=waiting");
  }

  listRecentDecisions(): Promise<RecentDecisionsResponse> {
    return this.request<RecentDecisionsResponse>("GET", "/v1/approvals?status=decided");
  }

  listDocuments(): Promise<DocumentListResponse> {
    return this.request<DocumentListResponse>("GET", "/v1/documents");
  }

  // Upload is multipart, not JSON: send FormData and let the browser set the multipart boundary
  // (so no JSON Content-Type header here). Returns the newly projected Document.
  async uploadDocument(evidenceKind: string, file: File): Promise<DocumentItem> {
    const form = new FormData();
    form.set("evidence_kind", evidenceKind);
    form.set("file", file);
    const res = await fetch("/v1/documents", {
      method: "POST",
      headers: { Authorization: `Bearer ${this.user.credential}` },
      body: form,
    });
    if (!res.ok) {
      const parsed = (await res.json().catch(() => null)) as { error?: { code?: string; message?: string } } | null;
      throw new ApiError(res.status, parsed?.error?.code ?? "upload_failed", parsed?.error?.message ?? `upload failed (${res.status})`);
    }
    return (await res.json()) as DocumentItem;
  }

  // Export returns bytes — fetched with the auth header, then turned into a download by the caller.
  async exportResult(id: string, format: string): Promise<Blob> {
    const res = await fetch(`/v1/missions/${id}/deliverable/export?format=${format}`, {
      headers: { Authorization: `Bearer ${this.user.credential}` },
    });
    if (!res.ok) {
      const parsed = (await res.json().catch(() => null)) as { error?: { message?: string } } | null;
      throw new ApiError(res.status, "export_failed", parsed?.error?.message ?? `export failed (${res.status})`);
    }
    return res.blob();
  }
}
