/**
 * Public entry point for the email module. Callers outside `lib/email/` should import from
 * here, not reach into `service.ts`/`client.ts`/`templates/*` directly.
 *
 * Adding a future email (password reset, report delivery, a notification) means: add a
 * `lib/email/templates/<name>.ts` that renders `{ subject, html, text }` (reuse
 * `renderEmailShell`/`renderButton` from `templates/layout.ts`), then add one small
 * `send<Name>Email` composer here that calls `sendEmail` — never a new Resend call site.
 */

import { sendEmail, type SendEmailResult } from "./service";
import { renderInvitationEmail, type InvitationEmailParams } from "./templates/invitation";

export { sendEmail, type SendEmailResult } from "./service";

export async function sendInvitationEmail(
  to: string,
  params: InvitationEmailParams,
): Promise<SendEmailResult> {
  const { subject, html, text } = renderInvitationEmail(params);
  return sendEmail({ to, subject, html, text });
}
