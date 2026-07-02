import type { Metadata } from "next";
import { Suspense } from "react";
import Link from "next/link";
import { LoginForm } from "@/components/auth/LoginForm";

export const metadata: Metadata = {
  title: "Sign in · Sentinel GRC",
  description: "Sign in to the Sentinel GRC governance, risk, compliance and AI platform.",
};

export default function LoginPage() {
  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background px-4 py-12">
      {/* Ambient accent wash, matching the workspace's restrained warm palette. */}
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-80 bg-accent-fade"
        aria-hidden
      />
      <Link
        href="/"
        className="absolute left-6 top-6 text-sm font-semibold tracking-tight text-foreground transition-opacity hover:opacity-80"
      >
        Sentinel GRC
      </Link>
      <div className="relative z-10 flex w-full justify-center">
        <Suspense fallback={null}>
          <LoginForm />
        </Suspense>
      </div>
      <p className="absolute bottom-6 text-2xs text-foreground-muted">
        © {new Date().getFullYear()} Sentinel GRC · Enterprise Edition
      </p>
    </main>
  );
}
