/**
 * Resend client singleton — the only place `RESEND_API_KEY` is read. Node-only; never import
 * this from a Client Component or anything that could end up in the browser bundle. Lazily
 * constructed (mirrors `lib/db/pool.ts`'s `getPool()`) so importing this module doesn't throw
 * in environments where email isn't configured (e.g. most tests).
 */

import { Resend } from "resend";

let client: Resend | null = null;

export function getResendClient(): Resend {
  if (!client) {
    const apiKey = process.env.RESEND_API_KEY;
    if (!apiKey) {
      throw new Error("RESEND_API_KEY is not set.");
    }
    client = new Resend(apiKey);
  }
  return client;
}

export function getEmailFromAddress(): string {
  const from = process.env.EMAIL_FROM;
  if (!from) {
    throw new Error("EMAIL_FROM is not set.");
  }
  return from;
}
