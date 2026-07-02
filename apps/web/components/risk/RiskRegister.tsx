"use client";

import { useMemo, useState, type FormEvent } from "react";
import { CheckCircle2, Loader2, Plus, ShieldAlert, Trash2, TriangleAlert } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Modal } from "@/components/ui/Modal";
import { ControlPicker } from "@/components/evidence/ControlPicker";
import { getControl } from "@/lib/frameworks/catalog";
import {
  useCreateRisk,
  useDeleteRisk,
  useRisk,
  useRisks,
  useTransitionRisk,
  useUpdateRisk,
} from "@/hooks/useRisks";
import {
  IMPACT_LABELS,
  LIKELIHOOD_LABELS,
  RISK_CATEGORIES,
  RISK_TRANSITIONS,
  scoreOf,
  severityOf,
  type RiskCategory,
  type RiskStatus,
  type RiskSummary,
  type Severity,
} from "@/lib/risk/types";
import { cn, formatDate } from "@/lib/utils";
import { toneBarClasses, tonePillClasses, toneSolidClasses, type Tone } from "@/lib/design/tone";

export interface RiskPermissions {
  canCreate: boolean;
  canUpdate: boolean;
  canAccept: boolean;
  canDelete: boolean;
}

const SEVERITY_LABEL: Record<Severity, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
  critical: "Critical",
};

/** Critical reads as a solid-fill badge (more urgent than the standard soft pill) — every
 * other severity maps straight onto the shared tone vocabulary. */
const SEVERITY_TONE: Record<Severity, Tone> = {
  low: "success",
  medium: "warning",
  high: "danger",
  critical: "danger",
};

function severityBadgeClass(severity: Severity): string {
  return severity === "critical"
    ? toneSolidClasses.danger
    : tonePillClasses[SEVERITY_TONE[severity]];
}

const STATUS_LABEL: Record<RiskStatus, string> = {
  open: "Open",
  mitigating: "Mitigating",
  accepted: "Accepted",
  closed: "Closed",
};

const STATUS_ACTION_LABEL: Record<RiskStatus, string> = {
  open: "Reopen",
  mitigating: "Start mitigation",
  accepted: "Accept risk",
  closed: "Close",
};

function SeverityBadge({ severity, score }: { severity: Severity; score: number }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-2xs font-medium",
        severityBadgeClass(severity),
      )}
    >
      {SEVERITY_LABEL[severity]} · {score}
    </span>
  );
}

const SEVERITIES: Severity[] = ["critical", "high", "medium", "low"];

export function RiskRegister(permissions: RiskPermissions) {
  const { data: risks, isLoading } = useRisks();
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [creating, setCreating] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);

  const stats = useMemo(() => {
    const list = risks ?? [];
    const bySeverity: Record<Severity, number> = { low: 0, medium: 0, high: 0, critical: 0 };
    let openCount = 0;
    let acceptedCount = 0;
    let scoreSum = 0;
    for (const risk of list) {
      bySeverity[risk.severity] += 1;
      if (risk.status === "open" || risk.status === "mitigating") openCount += 1;
      if (risk.status === "accepted") acceptedCount += 1;
      scoreSum += risk.inherentScore;
    }
    return {
      total: list.length,
      bySeverity,
      openCount,
      acceptedCount,
      avgScore: list.length ? Math.round((scoreSum / list.length) * 10) / 10 : 0,
    };
  }, [risks]);

  const filtered = (risks ?? []).filter(
    (risk) =>
      (statusFilter === "all" || risk.status === statusFilter) &&
      (severityFilter === "all" || risk.severity === severityFilter),
  );

  return (
    <div className="space-y-5">
      {/* Dashboard */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <div className="flex items-center gap-2 text-foreground-muted">
            <ShieldAlert className="h-4 w-4" strokeWidth={1.75} />
            <span className="text-2xs uppercase tracking-wider">Total risks</span>
          </div>
          <p className="mt-2 text-3xl font-semibold tracking-tight text-foreground">
            {stats.total}
          </p>
          <p className="mt-1 text-2xs text-foreground-muted">
            {stats.openCount} active · {stats.acceptedCount} accepted
          </p>
        </Card>
        <Card>
          <span className="text-2xs uppercase tracking-wider text-foreground-muted">
            Severity distribution
          </span>
          <div className="mt-3 space-y-1.5">
            {SEVERITIES.map((severity) => {
              const count = stats.bySeverity[severity];
              const width = stats.total ? Math.round((count / stats.total) * 100) : 0;
              return (
                <div key={severity} className="flex items-center gap-2">
                  <span className="w-14 text-2xs text-foreground-muted">
                    {SEVERITY_LABEL[severity]}
                  </span>
                  <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
                    <div
                      className={cn("h-full rounded-full", toneBarClasses[SEVERITY_TONE[severity]])}
                      style={{ width: `${width}%` }}
                    />
                  </div>
                  <span className="w-5 text-end text-2xs text-foreground-secondary">{count}</span>
                </div>
              );
            })}
          </div>
        </Card>
        <Card>
          <span className="text-2xs uppercase tracking-wider text-foreground-muted">
            Average inherent score
          </span>
          <p className="mt-2 text-3xl font-semibold tracking-tight text-foreground">
            {stats.avgScore}
          </p>
          <p className="mt-1 text-2xs text-foreground-muted">out of 25 (likelihood × impact)</p>
        </Card>
      </div>

      {/* Controls bar */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="h-9 rounded-lg border border-hairline bg-surface/60 px-3 text-sm text-foreground-secondary outline-none focus:border-hairline-strong"
        >
          <option value="all">All statuses</option>
          {Object.entries(STATUS_LABEL).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value)}
          className="h-9 rounded-lg border border-hairline bg-surface/60 px-3 text-sm text-foreground-secondary outline-none focus:border-hairline-strong"
        >
          <option value="all">All severities</option>
          {SEVERITIES.map((s) => (
            <option key={s} value={s}>
              {SEVERITY_LABEL[s]}
            </option>
          ))}
        </select>
        {permissions.canCreate && (
          <button
            type="button"
            onClick={() => setCreating(true)}
            className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-accent px-3.5 text-sm font-medium text-white shadow-glow transition-opacity duration-150 hover:opacity-90 active:scale-[0.98] sm:ms-auto"
          >
            <Plus className="h-4 w-4" strokeWidth={2} />
            New risk
          </button>
        )}
      </div>

      {isLoading ? (
        <Card className="flex items-center justify-center gap-2 py-12 text-sm text-foreground-muted">
          <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.75} />
          Loading risks…
        </Card>
      ) : filtered.length === 0 ? (
        <Card grain className="flex flex-col items-center gap-3 py-14 text-center">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-hairline-strong bg-surface-2">
            <TriangleAlert className="h-5 w-5 text-foreground-muted" strokeWidth={1.75} />
          </div>
          <p className="text-sm font-medium text-foreground">
            No risks{" "}
            {statusFilter !== "all" || severityFilter !== "all" ? "match the filters" : "yet"}
          </p>
          <p className="text-xs text-foreground-muted">
            {statusFilter !== "all" || severityFilter !== "all"
              ? "Try a different status or severity filter."
              : "Identify a risk and score it on the 5×5 matrix to get started."}
          </p>
        </Card>
      ) : (
        <Card flush>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="border-b border-hairline text-start text-2xs uppercase tracking-wider text-foreground-muted">
                  <th className="px-5 py-2.5 font-medium">Risk</th>
                  <th className="px-3 py-2.5 font-medium">Category</th>
                  <th className="px-3 py-2.5 font-medium">Inherent</th>
                  <th className="px-3 py-2.5 font-medium">Residual</th>
                  <th className="px-3 py-2.5 font-medium">Status</th>
                  <th className="px-3 py-2.5 font-medium">Owner</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((risk) => (
                  <tr
                    key={risk.id}
                    className="cursor-pointer border-b border-hairline last:border-0 hover:bg-white/[0.02]"
                    onClick={() => setDetailId(risk.id)}
                  >
                    <td className="px-5 py-3">
                      <p className="font-medium text-foreground">{risk.title}</p>
                      <p className="text-2xs text-foreground-muted">
                        {risk.controlCount} mitigating controls
                      </p>
                    </td>
                    <td className="px-3 py-3 capitalize text-foreground-secondary">
                      {risk.category.replace("_", " ")}
                    </td>
                    <td className="px-3 py-3">
                      <SeverityBadge severity={risk.severity} score={risk.inherentScore} />
                    </td>
                    <td className="px-3 py-3">
                      {risk.residualScore != null && risk.residualSeverity ? (
                        <SeverityBadge
                          severity={risk.residualSeverity}
                          score={risk.residualScore}
                        />
                      ) : (
                        <span className="text-2xs text-foreground-muted">—</span>
                      )}
                    </td>
                    <td className="px-3 py-3">
                      <span className="text-2xs text-foreground-secondary">
                        {STATUS_LABEL[risk.status]}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-foreground-secondary">{risk.ownerName}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {creating && <CreateRiskModal onClose={() => setCreating(false)} />}
      {detailId && (
        <RiskDetailModal
          id={detailId}
          permissions={permissions}
          onClose={() => setDetailId(null)}
        />
      )}
    </div>
  );
}

const inputClass =
  "w-full rounded-lg border border-hairline bg-surface/60 px-3 text-sm text-foreground outline-none focus:border-hairline-strong";

function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <span className="mb-1.5 block text-xs font-medium text-foreground-secondary">{children}</span>
  );
}

function ScaleSelect({
  value,
  onChange,
  labels,
}: {
  value: number;
  onChange: (n: number) => void;
  labels: readonly string[];
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(Number(e.target.value))}
      className={cn(inputClass, "h-9")}
    >
      {labels.map((label, i) => (
        <option key={label} value={i + 1}>
          {i + 1} · {label}
        </option>
      ))}
    </select>
  );
}

function ScorePreview({ likelihood, impact }: { likelihood: number; impact: number }) {
  const score = scoreOf(likelihood, impact);
  const severity = severityOf(score);
  return (
    <div className="flex items-center gap-2 rounded-lg border border-hairline bg-surface/40 px-3 py-2">
      <span className="text-2xs text-foreground-muted">Score</span>
      <span className="text-sm font-semibold text-foreground">{score}</span>
      <SeverityBadge severity={severity} score={score} />
    </div>
  );
}

function CreateRiskModal({ onClose }: { onClose: () => void }) {
  const create = useCreateRisk();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<RiskCategory>("cyber");
  const [likelihood, setLikelihood] = useState(3);
  const [impact, setImpact] = useState(3);
  const [ownerName, setOwnerName] = useState("");
  const [controlIds, setControlIds] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (!title.trim()) return setError("A title is required.");
    try {
      await create.mutateAsync({
        title,
        description,
        category,
        likelihood,
        impact,
        ownerName,
        controlIds,
      });
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create risk.");
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="New risk"
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
            form="create-risk-form"
            disabled={create.isPending}
            className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-accent px-3.5 text-sm font-medium text-white shadow-glow hover:opacity-90 active:scale-[0.98] disabled:opacity-60"
          >
            {create.isPending && <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2} />}
            Add to register
          </button>
        </>
      }
    >
      <form id="create-risk-form" onSubmit={onSubmit} className="space-y-4">
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
            placeholder="e.g. Unpatched internet-facing servers"
          />
        </label>
        <label className="block">
          <FieldLabel>Description</FieldLabel>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
            className={cn(inputClass, "resize-none py-2")}
          />
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <FieldLabel>Category</FieldLabel>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value as RiskCategory)}
              className={cn(inputClass, "h-9 capitalize")}
            >
              {RISK_CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c.replace("_", " ")}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <FieldLabel>Owner</FieldLabel>
            <input
              value={ownerName}
              onChange={(e) => setOwnerName(e.target.value)}
              className={cn(inputClass, "h-9")}
              placeholder="Defaults to you"
            />
          </label>
          <label className="block">
            <FieldLabel>Likelihood</FieldLabel>
            <ScaleSelect value={likelihood} onChange={setLikelihood} labels={LIKELIHOOD_LABELS} />
          </label>
          <label className="block">
            <FieldLabel>Impact</FieldLabel>
            <ScaleSelect value={impact} onChange={setImpact} labels={IMPACT_LABELS} />
          </label>
        </div>
        <ScorePreview likelihood={likelihood} impact={impact} />
        <div>
          <FieldLabel>Mitigating controls</FieldLabel>
          <ControlPicker value={controlIds} onChange={setControlIds} />
        </div>
      </form>
    </Modal>
  );
}

function RiskDetailModal({
  id,
  permissions,
  onClose,
}: {
  id: string;
  permissions: RiskPermissions;
  onClose: () => void;
}) {
  const { data: risk, isLoading } = useRisk(id);
  const update = useUpdateRisk();
  const transition = useTransitionRisk();
  const remove = useDeleteRisk();
  const [error, setError] = useState<string | null>(null);
  const [plan, setPlan] = useState<string | null>(null);

  if (isLoading || !risk) {
    return (
      <Modal open onClose={onClose} title="Risk">
        <div className="flex items-center justify-center gap-2 py-10 text-sm text-foreground-muted">
          <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.75} />
          Loading…
        </div>
      </Modal>
    );
  }

  const inherent = scoreOf(risk.likelihood, risk.impact);
  const transitions = RISK_TRANSITIONS[risk.status];
  const planValue = plan ?? risk.mitigationPlan ?? "";

  async function doTransition(status: RiskStatus) {
    setError(null);
    try {
      await transition.mutateAsync({ id, status });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Transition failed.");
    }
  }

  async function setResidual(field: "residualLikelihood" | "residualImpact", value: number) {
    await update.mutateAsync({ id, patch: { [field]: value } });
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={risk.title}
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
          <div className="flex flex-wrap items-center justify-end gap-2">
            {transitions.map((status) => {
              const isAccept = status === "accepted";
              const allowed = isAccept ? permissions.canAccept : permissions.canUpdate;
              if (!allowed) return null;
              return (
                <button
                  key={status}
                  type="button"
                  onClick={() => doTransition(status)}
                  disabled={transition.isPending}
                  className={cn(
                    "inline-flex h-8 items-center gap-1.5 rounded-lg px-3 text-2xs font-medium disabled:opacity-60",
                    isAccept
                      ? "bg-accent text-white shadow-glow hover:opacity-90 active:scale-[0.98]"
                      : "border border-hairline bg-surface/60 text-foreground-secondary hover:border-hairline-strong hover:text-foreground",
                  )}
                >
                  {isAccept && <CheckCircle2 className="h-3.5 w-3.5" strokeWidth={2} />}
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
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-white/[0.06] px-2 py-0.5 text-2xs capitalize text-foreground-secondary">
            {risk.category.replace("_", " ")}
          </span>
          <span className="text-2xs text-foreground-muted">Owner: {risk.ownerName}</span>
          <span className="text-2xs text-foreground-muted">
            Status: {STATUS_LABEL[risk.status]}
          </span>
          {risk.acceptedByName && (
            <span className="text-2xs text-warning">
              Accepted by {risk.acceptedByName}
              {risk.acceptedAt ? ` · ${formatDate(risk.acceptedAt)}` : ""}
            </span>
          )}
        </div>
        {risk.description && (
          <p className="text-sm text-foreground-secondary">{risk.description}</p>
        )}

        <div className="grid grid-cols-2 gap-4">
          <div className="rounded-lg border border-hairline bg-surface/40 p-3">
            <p className="text-2xs uppercase tracking-wider text-foreground-muted">Inherent risk</p>
            <div className="mt-2 flex items-center gap-2">
              <span className="text-2xl font-semibold text-foreground">{inherent}</span>
              <SeverityBadge severity={severityOf(inherent)} score={inherent} />
            </div>
            {permissions.canUpdate && (
              <div className="mt-2 grid grid-cols-2 gap-2">
                <label className="block">
                  <FieldLabel>Likelihood</FieldLabel>
                  <ScaleSelect
                    value={risk.likelihood}
                    onChange={(n) => update.mutate({ id, patch: { likelihood: n } })}
                    labels={LIKELIHOOD_LABELS}
                  />
                </label>
                <label className="block">
                  <FieldLabel>Impact</FieldLabel>
                  <ScaleSelect
                    value={risk.impact}
                    onChange={(n) => update.mutate({ id, patch: { impact: n } })}
                    labels={IMPACT_LABELS}
                  />
                </label>
              </div>
            )}
          </div>
          <div className="rounded-lg border border-hairline bg-surface/40 p-3">
            <p className="text-2xs uppercase tracking-wider text-foreground-muted">
              Residual risk (after controls)
            </p>
            <div className="mt-2 flex items-center gap-2">
              {risk.residualLikelihood != null && risk.residualImpact != null ? (
                (() => {
                  const residual = scoreOf(risk.residualLikelihood, risk.residualImpact);
                  return (
                    <>
                      <span className="text-2xl font-semibold text-foreground">{residual}</span>
                      <SeverityBadge severity={severityOf(residual)} score={residual} />
                    </>
                  );
                })()
              ) : (
                <span className="text-sm text-foreground-muted">Not assessed</span>
              )}
            </div>
            {permissions.canUpdate && (
              <div className="mt-2 grid grid-cols-2 gap-2">
                <label className="block">
                  <FieldLabel>Likelihood</FieldLabel>
                  <ScaleSelect
                    value={risk.residualLikelihood ?? risk.likelihood}
                    onChange={(n) => setResidual("residualLikelihood", n)}
                    labels={LIKELIHOOD_LABELS}
                  />
                </label>
                <label className="block">
                  <FieldLabel>Impact</FieldLabel>
                  <ScaleSelect
                    value={risk.residualImpact ?? risk.impact}
                    onChange={(n) => setResidual("residualImpact", n)}
                    labels={IMPACT_LABELS}
                  />
                </label>
              </div>
            )}
          </div>
        </div>

        <div>
          <FieldLabel>Mitigation plan</FieldLabel>
          {permissions.canUpdate ? (
            <>
              <textarea
                value={planValue}
                onChange={(e) => setPlan(e.target.value)}
                rows={3}
                className={cn(inputClass, "resize-none py-2")}
                placeholder="Describe the planned mitigations…"
              />
              {plan !== null && plan !== (risk.mitigationPlan ?? "") && (
                <button
                  type="button"
                  onClick={async () => {
                    await update.mutateAsync({ id, patch: { mitigationPlan: plan } });
                    setPlan(null);
                  }}
                  className="mt-2 inline-flex h-8 items-center gap-1 rounded-lg bg-accent px-2.5 text-2xs font-medium text-white"
                >
                  Save plan
                </button>
              )}
            </>
          ) : (
            <p className="whitespace-pre-wrap rounded-lg border border-hairline bg-surface/40 px-3 py-2 text-sm text-foreground-secondary">
              {risk.mitigationPlan || "No mitigation plan."}
            </p>
          )}
        </div>

        <div>
          <FieldLabel>Mitigating controls</FieldLabel>
          {risk.controlIds.length === 0 ? (
            <p className="text-2xs text-foreground-muted">No mapped controls.</p>
          ) : (
            <div className="flex flex-wrap gap-1">
              {risk.controlIds.map((cid) => {
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
