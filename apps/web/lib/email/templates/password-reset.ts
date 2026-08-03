/**
 * Password-reset email template. Bilingual — Arabic (RTL) first, then English (LTR) — same
 * convention as `templates/invitation.ts`; the account doesn't carry a preferred locale today.
 */

import { renderButton, renderEmailShell } from "./layout";

export interface PasswordResetEmailParams {
  name: string;
  resetLink: string;
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

export function renderPasswordResetEmail({
  name,
  resetLink,
}: PasswordResetEmailParams): RenderedEmail {
  const safeName = escapeHtml(name);
  const safeLink = escapeHtml(resetLink);

  const subject = "إعادة تعيين كلمة المرور في رشيد | Reset your Rasheed password";

  const arabicSection = `
    <div dir="rtl" lang="ar" style="text-align:right;font-family:Tahoma,Arial,sans-serif;">
      <h1 style="margin:0 0 16px;font-size:18px;color:#2b2015;">مرحبًا ${safeName}</h1>
      <p style="margin:0 0 16px;font-size:14px;line-height:1.8;color:#2b2015;">
        وصلنا طلب لإعادة تعيين كلمة المرور الخاصة بحسابك في رشيد.
      </p>
      <p style="margin:0 0 24px;font-size:14px;line-height:1.8;color:#2b2015;">
        يمكنك اختيار كلمة مرور جديدة عبر الرابط التالي:
      </p>
      <p style="margin:0 0 24px;">${renderButton("إعادة تعيين كلمة المرور", safeLink)}</p>
      <p style="margin:0 0 12px;font-size:13px;line-height:1.8;color:#6b5a47;">
        تنتهي صلاحية هذا الرابط خلال ساعة واحدة حفاظًا على أمان حسابك.
      </p>
      <p style="margin:0 0 20px;font-size:13px;line-height:1.8;color:#6b5a47;">
        إذا لم تطلب إعادة تعيين كلمة المرور، يمكنك تجاهل هذه الرسالة — لن يتغيّر شيء في حسابك.
      </p>
      <p style="margin:0;font-size:14px;color:#2b2015;">فريق رشيد</p>
    </div>`;

  const englishSection = `
    <div dir="ltr" lang="en" style="text-align:left;font-family:Arial,Helvetica,sans-serif;">
      <h1 style="margin:0 0 16px;font-size:18px;color:#2b2015;">Hello ${safeName},</h1>
      <p style="margin:0 0 16px;font-size:14px;line-height:1.7;color:#2b2015;">
        We received a request to reset the password for your Rasheed account.
      </p>
      <p style="margin:0 0 24px;font-size:14px;line-height:1.7;color:#2b2015;">
        Choose a new password using the link below:
      </p>
      <p style="margin:0 0 24px;">${renderButton("Reset password", safeLink)}</p>
      <p style="margin:0 0 12px;font-size:13px;line-height:1.7;color:#6b5a47;">
        For security reasons, this link expires in 1 hour.
      </p>
      <p style="margin:0 0 20px;font-size:13px;line-height:1.7;color:#6b5a47;">
        If you did not request a password reset, you can safely ignore this email — your
        account will not be changed.
      </p>
      <p style="margin:0;font-size:14px;color:#2b2015;">Rasheed Team</p>
    </div>`;

  const divider = `<hr style="margin:28px 0;border:none;border-top:1px solid rgba(59,44,31,0.14);" />`;

  const html = renderEmailShell({
    previewText: "Reset the password for your Rasheed account.",
    bodyHtml: `${arabicSection}${divider}${englishSection}`,
  });

  const text = [
    `مرحبًا ${name}`,
    "",
    "وصلنا طلب لإعادة تعيين كلمة المرور الخاصة بحسابك في رشيد.",
    "",
    "يمكنك اختيار كلمة مرور جديدة عبر الرابط التالي:",
    resetLink,
    "",
    "تنتهي صلاحية هذا الرابط خلال ساعة واحدة حفاظًا على أمان حسابك.",
    "",
    "إذا لم تطلب إعادة تعيين كلمة المرور، يمكنك تجاهل هذه الرسالة — لن يتغيّر شيء في حسابك.",
    "",
    "فريق رشيد",
    "",
    "----------------------------------------",
    "",
    `Hello ${name},`,
    "",
    "We received a request to reset the password for your Rasheed account.",
    "",
    "Choose a new password using the link below:",
    resetLink,
    "",
    "For security reasons, this link expires in 1 hour.",
    "",
    "If you did not request a password reset, you can safely ignore this email — your account",
    "will not be changed.",
    "",
    "Rasheed Team",
  ].join("\n");

  return { subject, html, text };
}
