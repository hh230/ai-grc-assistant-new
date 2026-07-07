/**
 * Generic, reusable transactional-email service (server-only), behind the Resend provider.
 * This is the one seam every future email goes through — invitations today; password reset,
 * report delivery, and notifications later reuse `sendEmail` and add their own template
 * under `lib/email/templates/`, never their own Resend call. Node-only: nothing here (or in
 * `client.ts`) is ever imported by a Client Component or middleware.
 */

import { getEmailFromAddress, getResendClient } from "./client";
import { logger } from "@/lib/observability/logger";

export interface SendEmailInput {
  to: string;
  subject: string;
  html: string;
  text: string;
}

export interface SendEmailResult {
  success: boolean;
  error?: string;
  /** The provider's message id, when available — useful for tracing a delivery in the
   * Resend dashboard/API without logging the email body anywhere. */
  id?: string;
}

/**
 * Sends one email. Never throws — a transactional email failing must not break the caller's
 * primary action (e.g. approving an access request still succeeds, and still shows the
 * invite link, even if the mail provider is unreachable or misconfigured). Callers inspect
 * the returned result to decide whether to surface a warning.
 */
export async function sendEmail(input: SendEmailInput): Promise<SendEmailResult> {
  try {
    const resend = getResendClient();
    const from = getEmailFromAddress();
    const { data, error } = await resend.emails.send({
      from,
      to: input.to,
      subject: input.subject,
      html: input.html,
      text: input.text,
    });
    if (error) {
      logger.error("email_send_failed", undefined, {
        to: input.to,
        subject: input.subject,
        providerError: error,
      });
      return { success: false, error: error.message };
    }
    logger.info("email_sent", { to: input.to, subject: input.subject, id: data?.id });
    return { success: true, id: data?.id };
  } catch (error) {
    logger.error("email_send_error", error, { to: input.to, subject: input.subject });
    return { success: false, error: error instanceof Error ? error.message : "Unknown error" };
  }
}
