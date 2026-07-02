/**
 * Canonical semantic tone vocabulary (V2-P3 design proposal §6 — component guidelines).
 * Single source of truth for tone→class mappings; components should compose from these
 * instead of hand-rolling their own tone records (previously duplicated across `Badge`,
 * `RiskRegister`'s `SEVERITY_STYLE`, and `RecentActivities`' `kindMeta`).
 */
export type Tone = "neutral" | "accent" | "success" | "warning" | "danger";

/** Soft pill treatment — tinted background, colored text, matching hairline border. */
export const tonePillClasses: Record<Tone, string> = {
  neutral: "bg-surface-elevated text-foreground-secondary border-hairline",
  accent: "bg-accent-soft text-accent-foreground border-accent/20",
  success: "bg-success-soft text-success border-success/20",
  warning: "bg-warning-soft text-warning border-warning/20",
  danger: "bg-danger-soft text-danger border-danger/20",
};

/**
 * Solid/emphasis treatment — full-color fill, white text. Reserved for the rare case a
 * tone needs to read as more urgent than the standard soft pill (e.g. "critical" severity).
 */
export const toneSolidClasses: Record<Tone, string> = {
  neutral: "bg-neutral text-white",
  accent: "bg-accent text-white",
  success: "bg-success text-white",
  warning: "bg-warning text-white",
  danger: "bg-danger text-white",
};

/** Icon-chip treatment — soft background, solid icon/text color, no border. */
export const toneIconClasses: Record<Tone, string> = {
  neutral: "text-foreground-secondary bg-neutral-soft",
  accent: "text-accent-foreground bg-accent-soft",
  success: "text-success bg-success-soft",
  warning: "text-warning bg-warning-soft",
  danger: "text-danger bg-danger-soft",
};

/** Progress/distribution-bar fill treatment — solid tone background, no text. */
export const toneBarClasses: Record<Tone, string> = {
  neutral: "bg-neutral",
  accent: "bg-accent",
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
};
