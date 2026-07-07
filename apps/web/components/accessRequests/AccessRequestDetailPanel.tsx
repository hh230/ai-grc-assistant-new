"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Check, Copy, Loader2, X } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { useApproveAccessRequest, useRejectAccessRequest } from "@/hooks/useAccessRequests";
import { INVITED_ROLES, type InvitedRole } from "@/lib/invitations/types";
import type { AccessRequest } from "@/lib/accessRequests/types";

interface AccessRequestDetailPanelProps {
  request: AccessRequest | null;
  onClose: () => void;
}

export function AccessRequestDetailPanel({ request, onClose }: AccessRequestDetailPanelProps) {
  const t = useTranslations("accessRequestsWorkspace.detail");
  const approveMutation = useApproveAccessRequest();
  const rejectMutation = useRejectAccessRequest();
  const [invitedRole, setInvitedRole] = useState<InvitedRole>("owner");
  const [inviteLink, setInviteLink] = useState<string | null>(null);
  const [rejected, setRejected] = useState(false);
  const [copied, setCopied] = useState(false);

  if (!request) {
    return (
      <Card>
        <p className="text-sm text-foreground-secondary">{t("empty")}</p>
      </Card>
    );
  }

  const handleApprove = async () => {
    const result = await approveMutation.mutateAsync({ id: request.id, invitedRole });
    setInviteLink(result.inviteLink);
  };

  const handleReject = async () => {
    await rejectMutation.mutateAsync(request.id);
    setRejected(true);
  };

  const handleCopy = async () => {
    if (!inviteLink) return;
    await navigator.clipboard.writeText(inviteLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const decided = Boolean(inviteLink) || rejected;

  return (
    <Card flush>
      <div className="border-b border-hairline p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-2xs font-medium uppercase tracking-wider text-foreground-muted">
              {request.roleTitle}
            </p>
            <h2 className="mt-1 text-sm font-semibold text-foreground">
              {request.organizationName}
            </h2>
            <p className="mt-0.5 text-xs text-foreground-muted">
              {request.name} · {request.email}
            </p>
          </div>
          {inviteLink ? (
            <Badge tone="success">{t("statusApproved")}</Badge>
          ) : rejected ? (
            <Badge tone="danger">{t("statusRejected")}</Badge>
          ) : (
            <Badge tone="warning">{t("statusPending")}</Badge>
          )}
        </div>
      </div>

      <div className="space-y-4 p-5">
        {request.message && (
          <div>
            <p className="text-2xs font-medium uppercase tracking-wider text-foreground-muted">
              {t("messageLabel")}
            </p>
            <p className="mt-1 text-sm text-foreground-secondary">{request.message}</p>
          </div>
        )}

        {inviteLink ? (
          <div className="rounded-lg border border-hairline bg-surface-elevated p-3">
            <p className="text-xs font-medium text-foreground-secondary">{t("inviteLinkLabel")}</p>
            <div className="mt-2 flex items-center gap-2">
              <input
                readOnly
                value={inviteLink}
                className="h-9 flex-1 truncate rounded-lg border border-hairline bg-surface px-3 text-xs text-foreground"
                dir="ltr"
                onFocus={(e) => e.currentTarget.select()}
              />
              <button
                type="button"
                onClick={handleCopy}
                className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-hairline px-3 text-xs font-medium text-foreground-secondary transition-colors hover:bg-surface-elevated"
              >
                {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                {copied ? t("copied") : t("copy")}
              </button>
            </div>
            <p className="mt-2 text-2xs text-foreground-muted">{t("inviteLinkHint")}</p>
          </div>
        ) : !rejected ? (
          <label className="block">
            <span className="mb-1.5 block text-xs font-medium text-foreground-secondary">
              {t("roleLabel")}
            </span>
            <select
              value={invitedRole}
              onChange={(e) => setInvitedRole(e.target.value as InvitedRole)}
              className="h-9 w-full rounded-lg border border-hairline bg-surface px-3 text-sm text-foreground outline-none focus:border-hairline-strong"
            >
              {INVITED_ROLES.map((role) => (
                <option key={role} value={role}>
                  {t(`roles.${role}`)}
                </option>
              ))}
            </select>
          </label>
        ) : null}
      </div>

      <div className="flex items-center justify-end gap-2 border-t border-hairline p-5">
        {decided ? (
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-hairline px-4 text-sm font-medium text-foreground-secondary transition-colors hover:bg-surface-elevated"
          >
            {t("close")}
          </button>
        ) : (
          <>
            <button
              type="button"
              onClick={handleReject}
              disabled={rejectMutation.isPending || approveMutation.isPending}
              className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-hairline px-4 text-sm font-medium text-foreground-secondary transition-colors hover:bg-surface-elevated disabled:cursor-not-allowed disabled:opacity-50"
            >
              {rejectMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <X className="h-4 w-4" strokeWidth={1.75} />
              )}
              {t("reject")}
            </button>
            <button
              type="button"
              onClick={handleApprove}
              disabled={approveMutation.isPending || rejectMutation.isPending}
              className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-accent px-4 text-sm font-medium text-white transition-colors hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {approveMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Check className="h-4 w-4" strokeWidth={1.75} />
              )}
              {t("approve")}
            </button>
          </>
        )}
      </div>
    </Card>
  );
}
