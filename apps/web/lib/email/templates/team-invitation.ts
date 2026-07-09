/**
 * Team invitation email — an owner/admin invites a colleague directly into their existing
 * organization (as opposed to `invitation.ts`, which is for the original "your access request
 * was approved" flow). Bilingual — Arabic (RTL) first, then English (LTR) — matching
 * `invitation.ts`'s convention. Only the name, organization, and invite link are interpolated.
 */

import { renderButton, renderEmailShell } from "./layout";

export interface TeamInvitationEmailParams {
  organizationName: string;
  inviteLink: string;
}

export interface RenderedEmail {
  subject: string;
  html: string;
  text: string;
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function renderTeamInvitationEmail({
  organizationName,
  inviteLink,
}: TeamInvitationEmailParams): RenderedEmail {
  const safeOrg = escapeHtml(organizationName);
  const safeLink = escapeHtml(inviteLink);

  const subject = `دعوة للانضمام إلى ${organizationName} على رشيد | You've been invited to join ${organizationName} on Rasheed`;

  const arabicSection = `
    <div dir="rtl" lang="ar" style="text-align:right;font-family:Tahoma,Arial,sans-serif;">
      <h1 style="margin:0 0 16px;font-size:18px;color:#2b2015;">مرحبًا</h1>
      <p style="margin:0 0 16px;font-size:14px;line-height:1.8;color:#2b2015;">
        تمت دعوتك للانضمام إلى مساحة عمل <strong>${safeOrg}</strong> على منصة رشيد.
      </p>
      <p style="margin:0 0 24px;font-size:14px;line-height:1.8;color:#2b2015;">
        يمكنك الآن إنشاء حسابك والانضمام إلى الفريق عبر الرابط التالي:
      </p>
      <p style="margin:0 0 24px;">${renderButton("الانضمام إلى الفريق", safeLink)}</p>
      <p style="margin:0 0 12px;font-size:13px;line-height:1.8;color:#6b5a47;">
        تنتهي صلاحية رابط الدعوة خلال 7 أيام حفاظًا على أمان الحساب.
      </p>
      <p style="margin:0 0 20px;font-size:13px;line-height:1.8;color:#6b5a47;">
        إذا لم تكن تتوقع هذه الدعوة، يمكنك تجاهل هذه الرسالة.
      </p>
      <p style="margin:0;font-size:14px;color:#2b2015;">فريق رشيد</p>
    </div>`;

  const englishSection = `
    <div dir="ltr" lang="en" style="text-align:left;font-family:Arial,Helvetica,sans-serif;">
      <h1 style="margin:0 0 16px;font-size:18px;color:#2b2015;">Hello,</h1>
      <p style="margin:0 0 16px;font-size:14px;line-height:1.7;color:#2b2015;">
        You've been invited to join <strong>${safeOrg}</strong>'s workspace on Rasheed.
      </p>
      <p style="margin:0 0 24px;font-size:14px;line-height:1.7;color:#2b2015;">
        You can now create your account and join the team using the link below:
      </p>
      <p style="margin:0 0 24px;">${renderButton("Join the team", safeLink)}</p>
      <p style="margin:0 0 12px;font-size:13px;line-height:1.7;color:#6b5a47;">
        For security reasons, this invitation link expires in 7 days.
      </p>
      <p style="margin:0 0 20px;font-size:13px;line-height:1.7;color:#6b5a47;">
        If you weren't expecting this invitation, you can ignore this email.
      </p>
      <p style="margin:0;font-size:14px;color:#2b2015;">Rasheed Team</p>
    </div>`;

  const divider = `<hr style="margin:28px 0;border:none;border-top:1px solid rgba(59,44,31,0.14);" />`;

  const html = renderEmailShell({
    previewText: `You've been invited to join ${organizationName} on Rasheed.`,
    bodyHtml: `${arabicSection}${divider}${englishSection}`,
  });

  const text = [
    "مرحبًا",
    "",
    `تمت دعوتك للانضمام إلى مساحة عمل ${organizationName} على منصة رشيد.`,
    "",
    "يمكنك الآن إنشاء حسابك والانضمام إلى الفريق عبر الرابط التالي:",
    inviteLink,
    "",
    "تنتهي صلاحية رابط الدعوة خلال 7 أيام حفاظًا على أمان الحساب.",
    "",
    "إذا لم تكن تتوقع هذه الدعوة، يمكنك تجاهل هذه الرسالة.",
    "",
    "فريق رشيد",
    "",
    "----------------------------------------",
    "",
    "Hello,",
    "",
    `You've been invited to join ${organizationName}'s workspace on Rasheed.`,
    "",
    "You can now create your account and join the team using the link below:",
    inviteLink,
    "",
    "For security reasons, this invitation link expires in 7 days.",
    "",
    "If you weren't expecting this invitation, you can ignore this email.",
    "",
    "Rasheed Team",
  ].join("\n");

  return { subject, html, text };
}
