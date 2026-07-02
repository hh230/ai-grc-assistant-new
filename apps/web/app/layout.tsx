import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sentinel GRC",
  description:
    "Enterprise Governance, Risk, Compliance and AI platform — real-time posture across regulated frameworks.",
};

export const viewport: Viewport = {
  themeColor: "#fbf8f3",
};

// The root layout is intentionally shell-free: the authenticated workspace shell lives in
// the `(app)` route group, while public routes (e.g. /login) render on their own.
// `lang`/`dir` become locale-driven once next-intl lands in V2-P2; single "en" for now.
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" dir="ltr">
      <body className="min-h-screen bg-background font-sans text-foreground antialiased">
        {children}
      </body>
    </html>
  );
}
