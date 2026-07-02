"use client";

import { useState, type FormEvent } from "react";
import { CheckCircle2, FileText, Loader2, Plus, ShieldCheck, Trash2, TriangleAlert } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Modal } from "@/components/ui/Modal";
import { ControlPicker } from "@/components/evidence/ControlPicker";
import {
  useCreatePolicy,
  useDeletePolicy,
  usePolicies,
  usePolicy,
  useTransitionPolicy,
  useUpdatePolicy,
} from "@/hooks/usePolicies";
import { getControl } from "@/lib/frameworks/catalog";
import { POLICY_TRANSITIONS, type PolicyStatus, type PolicySummary } from "@/lib/policies/types";
import { cn, formatDate } from "@/lib/utils";

export interface PolicyPermissions {
  canCreate: boolean;
  canUpdate: boolean;
  canPublish: boolean;
  canDelete: boolean;
}

const STATUS_STYLE: Record<PolicyStatus, { label: string; className: string }> = {
  draft: { label: "Draft", className: "bg-white/[0.06] text-foreground-muted" },
  in_review: { label: "In review", className: "bg-warning-soft text-warning" },
  published: { label: "Published", className: "bg-success-soft text-success" },
  archived: { label: "Archived", className: "bg-white/[0.04] text-foreground-muted" },
};

const STATUS_ACTION_LABEL: Record<PolicyStatus, string> = {
  draft: "Move to draft",
  in_review: "Submit for review",
  published: "Publish",
  archived: "Archive",
};

export function PolicyStatusBadge({ status }: { status: PolicyStatus }) {
  const style = STATUS_STYLE[status];
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-2xs font-medium",
        style.className,
      )}
    >
      {style.label}
    </span>
  );
}

export function PoliciesWorkspace(permissions: PolicyPermissions) {
  const { data: policies, isLoading } = usePolicies();
  const [creating, setCreating] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <p className="text-2xs text-foreground-muted">{policies?.length ?? 0} policies</p>
        {permissions.canCreate && (
          <button
            type="button"
            onClick={() => setCreating(true)}
            className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-accent px-3.5 text-sm font-medium text-white shadow-glow transition-opacity duration-150 hover:opacity-90 active:scale-[0.98]"
          >
            <Plus className="h-4 w-4" strokeWidth={2} />
            New policy
          </button>
        )}
      </div>

      {isLoading ? (
        <Card className="flex items-center justify-center gap-2 py-12 text-sm text-foreground-muted">
          <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.75} />
          Loading policies…
        </Card>
      ) : !policies || policies.length === 0 ? (
        <Card grain className="flex flex-col items-center gap-3 py-14 text-center">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-hairline-strong bg-surface-2">
            <FileText className="h-5 w-5 text-foreground-muted" strokeWidth={1.75} />
          </div>
          <p className="text-sm font-medium text-foreground">No policies yet</p>
          <p className="text-xs text-foreground-muted">
            Author a policy and map it to the controls it governs.
          </p>
        </Card>
      ) : (
        <div className="grid gap-3">
          {policies.map((policy) => (
            <PolicyRow key={policy.id} policy={policy} onOpen={() => setDetailId(policy.id)} />
          ))}
        </div>
      )}

      {creating && <CreatePolicyModal onClose={() => setCreating(false)} />}
      {detailId && (
        <PolicyDetailModal
          id={detailId}
          permissions={permissions}
          onClose={() => setDetailId(null)}
        />
      )}
    </div>
  );
}

function PolicyRow({ policy, onOpen }: { policy: PolicySummary; onOpen: () => void }) {
  return (
    <Card>
      <button type="button" onClick={onOpen} className="flex w-full items-center gap-3 text-start">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-hairline bg-surface-2">
          <ShieldCheck className="h-4 w-4 text-foreground-secondary" strokeWidth={1.75} />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-foreground">{policy.title}</p>
          <p className="truncate text-2xs text-foreground-muted">
            {policy.ownerName} · {policy.controlCount} controls · Updated{" "}
            {formatDate(policy.updatedAt)}
          </p>
        </div>
        <PolicyStatusBadge status={policy.status} />
      </button>
    </Card>
  );
}

function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <span className="mb-1.5 block text-xs font-medium text-foreground-secondary">{children}</span>
  );
}

const inputClass =
  "w-full rounded-lg border border-hairline bg-surface/60 px-3 text-sm text-foreground outline-none focus:border-hairline-strong";

function CreatePolicyModal({ onClose }: { onClose: () => void }) {
  const create = useCreatePolicy();
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [body, setBody] = useState("");
  const [controlIds, setControlIds] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (!title.trim()) return setError("A title is required.");
    try {
      await create.mutateAsync({ title, summary, body, controlIds });
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create policy.");
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="New policy"
      description="Drafts start in Draft and move through review before publication."
      size="lg"
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className="h-9 rounded-lg border border-hairline bg-surface/60 px-3 text-sm text-foreground-secondary hover:text-foreground"
          >
            Cancel
          </button>
          <button
            type="submit"
            form="create-policy-form"
            disabled={create.isPending}
            className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-accent px-3.5 text-sm font-medium text-white shadow-glow hover:opacity-90 disabled:opacity-60"
          >
            {create.isPending && <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2} />}
            Create draft
          </button>
        </>
      }
    >
      <form id="create-policy-form" onSubmit={onSubmit} className="space-y-4">
        {error && (
          <div className="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger">
            <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={1.75} />
            <span>{error}</span>
          </div>
        )}
        <label className="block">
          <FieldLabel>Title</FieldLabel>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className={cn(inputClass, "h-9")}
            placeholder="e.g. Access Control Policy"
          />
        </label>
        <label className="block">
          <FieldLabel>Summary</FieldLabel>
          <input
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            className={cn(inputClass, "h-9")}
            placeholder="One-line purpose"
          />
        </label>
        <label className="block">
          <FieldLabel>Body</FieldLabel>
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={5}
            className={cn(inputClass, "resize-none py-2")}
            placeholder="Policy text…"
          />
        </label>
        <div>
          <FieldLabel>Mapped controls</FieldLabel>
          <ControlPicker value={controlIds} onChange={setControlIds} />
        </div>
      </form>
    </Modal>
  );
}

function PolicyDetailModal({
  id,
  permissions,
  onClose,
}: {
  id: string;
  permissions: PolicyPermissions;
  onClose: () => void;
}) {
  const { data: policy, isLoading } = usePolicy(id);
  const update = useUpdatePolicy();
  const transition = useTransitionPolicy();
  const remove = useDeletePolicy();
  const [body, setBody] = useState<string | null>(null);
  const [editingControls, setEditingControls] = useState(false);
  const [draftControls, setDraftControls] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  if (isLoading || !policy) {
    return (
      <Modal open onClose={onClose} title="Policy">
        <div className="flex items-center justify-center gap-2 py-10 text-sm text-foreground-muted">
          <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.75} />
          Loading…
        </div>
      </Modal>
    );
  }

  const bodyValue = body ?? policy.body ?? "";
  const transitions = POLICY_TRANSITIONS[policy.status];

  async function doTransition(status: PolicyStatus) {
    setError(null);
    try {
      await transition.mutateAsync({ id, status });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Transition failed.");
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={policy.title}
      size="lg"
      footer={
        <div className="flex w-full items-center justify-between">
          {permissions.canDelete ? (
            <button
              type="button"
              onClick={async () => {
                await remove.mutateAsync(id);
                onClose();
              }}
              className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-hairline bg-surface/60 px-2.5 text-2xs font-medium text-foreground-muted hover:border-danger/40 hover:text-danger"
            >
              <Trash2 className="h-3.5 w-3.5" strokeWidth={1.75} />
              Delete
            </button>
          ) : (
            <span />
          )}
          <div className="flex items-center gap-2">
            {transitions.map((status) => {
              const isPublish = status === "published";
              const allowed = isPublish ? permissions.canPublish : permissions.canUpdate;
              if (!allowed) return null;
              return (
                <button
                  key={status}
                  type="button"
                  onClick={() => doTransition(status)}
                  disabled={transition.isPending}
                  className={cn(
                    "inline-flex h-8 items-center gap-1.5 rounded-lg px-3 text-2xs font-medium disabled:opacity-60",
                    isPublish
                      ? "bg-accent text-white shadow-glow hover:opacity-90 active:scale-[0.98]"
                      : "border border-hairline bg-surface/60 text-foreground-secondary hover:border-hairline-strong hover:text-foreground",
                  )}
                >
                  {isPublish && <CheckCircle2 className="h-3.5 w-3.5" strokeWidth={2} />}
                  {STATUS_ACTION_LABEL[status]}
                </button>
              );
            })}
          </div>
        </div>
      }
    >
      <div className="space-y-4">
        {error && (
          <div className="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger">
            <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={1.75} />
            <span>{error}</span>
          </div>
        )}
        <div className="flex items-center gap-2">
          <PolicyStatusBadge status={policy.status} />
          <span className="text-2xs text-foreground-muted">Owner: {policy.ownerName}</span>
          {policy.approvedByName && (
            <span className="text-2xs text-success">
              Published by {policy.approvedByName}
              {policy.approvedAt ? ` · ${formatDate(policy.approvedAt)}` : ""}
            </span>
          )}
        </div>
        {policy.summary && <p className="text-sm text-foreground-secondary">{policy.summary}</p>}

        <div>
          <FieldLabel>Body</FieldLabel>
          {permissions.canUpdate ? (
            <>
              <textarea
                value={bodyValue}
                onChange={(e) => setBody(e.target.value)}
                rows={6}
                className={cn(inputClass, "resize-none py-2")}
              />
              {body !== null && body !== (policy.body ?? "") && (
                <button
                  type="button"
                  onClick={async () => {
                    await update.mutateAsync({ id, patch: { body } });
                    setBody(null);
                  }}
                  className="mt-2 inline-flex h-8 items-center gap-1 rounded-lg bg-accent px-2.5 text-2xs font-medium text-white"
                >
                  {update.isPending && <Loader2 className="h-3 w-3 animate-spin" strokeWidth={2} />}
                  Save body
                </button>
              )}
            </>
          ) : (
            <p className="whitespace-pre-wrap rounded-lg border border-hairline bg-surface/40 px-3 py-2 text-sm text-foreground-secondary">
              {policy.body || "No body."}
            </p>
          )}
        </div>

        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <FieldLabel>Mapped controls</FieldLabel>
            {permissions.canUpdate && !editingControls && (
              <button
                type="button"
                onClick={() => {
                  setDraftControls(policy.controlIds);
                  setEditingControls(true);
                }}
                className="text-2xs text-accent-foreground hover:underline"
              >
                Edit
              </button>
            )}
          </div>
          {editingControls ? (
            <div className="space-y-2">
              <ControlPicker value={draftControls} onChange={setDraftControls} />
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setEditingControls(false)}
                  className="h-8 rounded-lg border border-hairline px-2.5 text-2xs text-foreground-secondary"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={async () => {
                    await update.mutateAsync({ id, patch: { controlIds: draftControls } });
                    setEditingControls(false);
                  }}
                  className="inline-flex h-8 items-center gap-1 rounded-lg bg-accent px-2.5 text-2xs font-medium text-white"
                >
                  Save
                </button>
              </div>
            </div>
          ) : policy.controlIds.length === 0 ? (
            <p className="text-2xs text-foreground-muted">No mapped controls.</p>
          ) : (
            <div className="flex flex-wrap gap-1">
              {policy.controlIds.map((cid) => {
                const control = getControl(cid);
                return (
                  <span
                    key={cid}
                    className="inline-flex items-center gap-1 rounded-full border border-hairline bg-surface/60 px-1.5 py-0.5 text-2xs text-foreground-secondary"
                  >
                    <span className="text-accent-foreground">
                      {control?.frameworkShortName ?? "?"}
                    </span>
                    {control?.code ?? cid}
                  </span>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
}
