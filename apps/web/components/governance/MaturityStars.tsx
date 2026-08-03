/** The shared star-rating glyph (0–5 filled/hollow stars) — used everywhere a maturity rating is
 * shown: the pre-approval Report's Current Maturity / Governance Vision sections and the live
 * Plan's Maturity Journey (`components/plan/MaturityJourney.tsx`). One definition, not three. */
export function MaturityStars({ stars, muted = false }: { stars: number; muted?: boolean }) {
  return (
    <span
      aria-hidden
      className={`tracking-tight ${muted ? "text-foreground-muted" : "text-accent-foreground"}`}
    >
      {"★".repeat(stars)}
      <span className="text-hairline-strong">{"☆".repeat(5 - stars)}</span>
    </span>
  );
}
