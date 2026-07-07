/**
 * Invitation email template (KI-P9 access onboarding). Bilingual — Arabic (RTL) first, then
 * English (LTR) — since Rasheed serves both audiences and the invitation doesn't carry a
 * preferred locale today. Copy is fixed, professional, and matches the product's approved
 * wording; only the name and the invite link are interpolated.
 */

import { renderButton, renderEmailShell } from "./layout";

export interface InvitationEmailParams {
  name: string;
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

export function renderInvitationEmail({ name, inviteLink }: InvitationEmailParams): RenderedEmail {
  const safeName = escapeHtml(name);
  const safeLink = escapeHtml(inviteLink);

  const subject =
    "تمت الموافقة على طلب الوصول إلى رشيد | Your Rasheed access request has been approved";

  const arabicSection = `
    <div dir="rtl" lang="ar" style="text-align:right;font-family:Tahoma,Arial,sans-serif;">
      <h1 style="margin:0 0 16px;font-size:18px;color:#2b2015;">مرحبًا ${safeName}</h1>
      <p style="margin:0 0 16px;font-size:14px;line-height:1.8;color:#2b2015;">
        يسعدنا إبلاغك بأنه تمت الموافقة على طلب انضمامك إلى منصة رشيد.
      </p>
      <p style="margin:0 0 24px;font-size:14px;line-height:1.8;color:#2b2015;">
        يمكنك الآن إنشاء حسابك وتفعيل الوصول إلى مساحة عملك عبر الرابط التالي:
      </p>
      <p style="margin:0 0 24px;">${renderButton("تفعيل الحساب", safeLink)}</p>
      <p style="margin:0 0 12px;font-size:13px;line-height:1.8;color:#6b5a47;">
        تنتهي صلاحية رابط الدعوة خلال 7 أيام حفاظًا على أمان الحساب.
      </p>
      <p style="margin:0 0 20px;font-size:13px;line-height:1.8;color:#6b5a47;">
        إذا لم تقم بطلب الوصول، يمكنك تجاهل هذه الرسالة.
      </p>
      <p style="margin:0;font-size:14px;color:#2b2015;">فريق رشيد</p>
    </div>`;

  const englishSection = `
    <div dir="ltr" lang="en" style="text-align:left;font-family:Arial,Helvetica,sans-serif;">
      <h1 style="margin:0 0 16px;font-size:18px;color:#2b2015;">Hello ${safeName},</h1>
      <p style="margin:0 0 16px;font-size:14px;line-height:1.7;color:#2b2015;">
        Your request to join Rasheed has been approved.
      </p>
      <p style="margin:0 0 24px;font-size:14px;line-height:1.7;color:#2b2015;">
        You can now activate your account and create your workspace using the link below:
      </p>
      <p style="margin:0 0 24px;">${renderButton("Activate account", safeLink)}</p>
      <p style="margin:0 0 12px;font-size:13px;line-height:1.7;color:#6b5a47;">
        For security reasons, this invitation link expires in 7 days.
      </p>
      <p style="margin:0 0 20px;font-size:13px;line-height:1.7;color:#6b5a47;">
        If you did not request access, you can ignore this email.
      </p>
      <p style="margin:0;font-size:14px;color:#2b2015;">Rasheed Team</p>
    </div>`;

  const divider = `<hr style="margin:28px 0;border:none;border-top:1px solid rgba(59,44,31,0.14);" />`;

  const html = renderEmailShell({
    previewText: "Your Rasheed access request has been approved.",
    bodyHtml: `${arabicSection}${divider}${englishSection}`,
  });

  const text = [
    `مرحبًا ${name}`,
    "",
    "يسعدنا إبلاغك بأنه تمت الموافقة على طلب انضمامك إلى منصة رشيد.",
    "",
    "يمكنك الآن إنشاء حسابك وتفعيل الوصول إلى مساحة عملك عبر الرابط التالي:",
    inviteLink,
    "",
    "تنتهي صلاحية رابط الدعوة خلال 7 أيام حفاظًا على أمان الحساب.",
    "",
    "إذا لم تقم بطلب الوصول، يمكنك تجاهل هذه الرسالة.",
    "",
    "فريق رشيد",
    "",
    "----------------------------------------",
    "",
    `Hello ${name},`,
    "",
    "Your request to join Rasheed has been approved.",
    "",
    "You can now activate your account and create your workspace using the link below:",
    inviteLink,
    "",
    "For security reasons, this invitation link expires in 7 days.",
    "",
    "If you did not request access, you can ignore this email.",
    "",
    "Rasheed Team",
  ].join("\n");

  return { subject, html, text };
}
