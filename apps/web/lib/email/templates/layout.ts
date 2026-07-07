/**
 * Shared HTML email shell — table-based layout (email-client safe, no external stylesheet)
 * matching Rasheed's brand palette (`app/globals.css`'s `--bg`/`--accent`/`--text` tokens).
 * Every template under `lib/email/templates/` renders its content into this shell instead of
 * hand-rolling its own `<html>` document, so a future password-reset/report/notification
 * email looks consistent with zero extra styling work.
 */

const COLORS = {
  bg: "#fbf8f3",
  surface: "#ffffff",
  border: "rgba(59, 44, 31, 0.14)",
  text: "#2b2015",
  textMuted: "#6b5a47",
  accent: "#5b3a22",
  accentText: "#ffffff",
};

export interface EmailShellOptions {
  /** Short hidden preview text shown in inbox lists (before the subject is opened). */
  previewText: string;
  /** Pre-rendered inner HTML — one or more content sections. */
  bodyHtml: string;
}

export function renderEmailShell({ previewText, bodyHtml }: EmailShellOptions): string {
  return `<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Rasheed</title>
  </head>
  <body style="margin:0;padding:0;background-color:${COLORS.bg};font-family:Arial,Helvetica,sans-serif;">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;">${previewText}</div>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:${COLORS.bg};padding:32px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background-color:${COLORS.surface};border:1px solid ${COLORS.border};border-radius:16px;overflow:hidden;">
            <tr>
              <td style="padding:28px 32px;border-bottom:1px solid ${COLORS.border};">
                <span style="font-size:20px;font-weight:700;color:${COLORS.text};letter-spacing:-0.3px;">Rasheed</span>
              </td>
            </tr>
            <tr>
              <td style="padding:32px;">${bodyHtml}</td>
            </tr>
            <tr>
              <td style="padding:20px 32px;border-top:1px solid ${COLORS.border};">
                <p style="margin:0;font-size:12px;color:${COLORS.textMuted};text-align:center;">
                  © ${new Date().getFullYear()} Rasheed · Enterprise Edition
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>`;
}

export function renderButton(label: string, href: string): string {
  return `<a href="${href}" style="display:inline-block;background-color:${COLORS.accent};color:${COLORS.accentText};text-decoration:none;font-size:14px;font-weight:600;padding:12px 24px;border-radius:8px;">${label}</a>`;
}

export const emailColors = COLORS;
