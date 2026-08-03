/** Browser-side Forgot/Reset Password API client — calls this app's own routes under
 * `/api/auth/forgot-password` and `/api/auth/reset-password/[token]`. */

async function parseError(response: Response): Promise<string> {
  const data = (await response.json().catch(() => ({}))) as { error?: string };
  return data.error ?? `Request failed (${response.status}).`;
}

export async function requestPasswordReset(email: string): Promise<void> {
  const response = await fetch("/api/auth/forgot-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (!response.ok) throw new Error(await parseError(response));
}

export interface ResetTokenPreviewDto {
  email: string;
}

export async function fetchResetTokenPreview(token: string): Promise<ResetTokenPreviewDto> {
  const response = await fetch(`/api/auth/reset-password/${encodeURIComponent(token)}`, {
    cache: "no-store",
  });
  if (!response.ok) throw new Error(await parseError(response));
  return ((await response.json()) as { reset: ResetTokenPreviewDto }).reset;
}

export async function resetPassword(token: string, password: string): Promise<void> {
  const response = await fetch(`/api/auth/reset-password/${encodeURIComponent(token)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  if (!response.ok) throw new Error(await parseError(response));
}
