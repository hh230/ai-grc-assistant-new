# Design System — Version 2

Living reference for the Sentinel GRC visual language. Update this file whenever a token,
primitive, or rule changes — component code should never disagree with what's written here.

## Philosophy

Premium, minimal, enterprise. The product reads as **Microsoft Purview / Stripe Dashboard /
Linear / Notion**, never as an AI chatbot, a developer dashboard, or a technical prototype.
Calm, low-saturation, warm palette. Generous spacing. Cards breathe. No neon, no gaming-style UI.

## Color tokens

All colors are CSS variables (`apps/web/app/globals.css`), consumed through Tailwind theme
extensions (`apps/web/tailwind.config.ts`) — never hardcode a hex value in a component.

| Token | Value | Tailwind class(es) | Usage |
|---|---|---|---|
| `--bg` | `#FBF8F3` | `bg-background` | App background |
| `--canvas` | `#F5EFE6` | `bg-canvas` | Secondary background, marketing hero sections |
| `--surface` | `#FFFFFF` | `bg-surface` | Cards, panels |
| `--surface-2` | `#F3ECE0` | `bg-surface-elevated` | Nested/elevated surfaces |
| `--surface-hover` | `#EFE6D8` | `bg-surface-hover` | Hover state |
| `--border` | `rgba(59,44,31,.10)` | `border-hairline` | Hairline dividers |
| `--border-strong` | `rgba(59,44,31,.18)` | `border-hairline-strong` | Emphasized hairline |
| `--text` | `#2B2015` | `text-foreground` | Primary text |
| `--text-2` | `#6B5A47` | `text-foreground-secondary` | Secondary text |
| `--text-3` | `#9C8B78` | `text-foreground-muted` | Tertiary/placeholder text |
| `--accent` | `#5B3A22` | `bg-accent` / `text-accent` | Primary buttons, links, active nav |
| `--accent-soft` | `rgba(91,58,34,.08)` | `bg-accent-soft` | Active/hover backgrounds |
| `--accent-fg` | `#3D2716` | `text-accent-foreground` | Text on `accent-soft` |
| `--gold` | `#B8923F` | `text-gold` / `border-gold` | **Decorative only** — see rule below |
| `--success` | `#3F8F5C` | `bg-success` / `text-success` | Positive status |
| `--warning` | `#B8792E` | `bg-warning` / `text-warning` | Caution status |
| `--danger` | `#B23A34` | `bg-danger` / `text-danger` | Negative/blocking status |

**Gold usage rule:** gold is an accent, never a fill. Allowed: small icon/text highlights on
"AI-generated" or "premium" badges, a 1–2px active-tab underline, a subtle ring on a single
featured card. Never: button backgrounds, body text, large fills, or more than ~10% of any
single screen. If a design needs "make it pop," reach for the dark-brown `accent`, not gold.

Dark mode has been removed. This is a single light theme.

## Typography

- **Latin:** Inter (`font-sans`). Feature settings `cv11, ss01` already applied globally.
- **Arabic:** Tajawal (`font-sans-arabic`), wired to the `ar` locale in V2-P2. Fallback: IBM Plex
  Sans Arabic if Tajawal reads too geometric in review.
- Body line-height: `1.6` (set globally on `body`). Don't override to `1.5` or below for
  paragraph copy — the brief calls for "comfortable reading."
- Weight convention: 400 body, 500 label, 600 card title, 700 heading.
- Card internal padding: `p-6` minimum, `p-8` for hero/feature cards. Avoid `p-4` or tighter on
  any card containing prose.

## Spacing & shape

- Tailwind's default 4px scale — no custom scale needed, just use generous multiples (prefer
  `gap-6`/`gap-8` over `gap-2`/`gap-3` for card grids).
- Corner radius: `rounded-2xl` default for cards/modals, `rounded-4xl` (custom, 1.75rem) for
  hero/feature showcase blocks.
- Shadows: `shadow-soft` (resting card), `shadow-elevated` (modal/popover), `shadow-glow`
  (focused/featured state) — all pre-tuned to the warm palette, don't hand-roll new `rgba()`
  shadows in components.

## RTL / bidi rules (binding once V2-P2 lands)

- Never use physical spacing/position utilities (`ml-`, `mr-`, `pl-`, `pr-`, `left-`, `right-`,
  `text-left`, `text-right`) in new or edited components. Use logical equivalents (`ms-`, `me-`,
  `ps-`, `pe-`, `start-`, `end-`, `text-start`, `text-end`) — they flip automatically with the
  document's `dir` attribute.
- Direction-sensitive icons (arrows, chevrons that imply "forward/back") get the `.flip-rtl`
  utility class (defined in `globals.css`), which mirrors them under `[dir="rtl"]`. Icons with no
  inherent direction (checkmarks, shields, file icons) never need it.
- `<html dir="ltr">` for `en`, `dir="rtl"` for `ar` — set once at the locale-root layout, never
  per-component.

## Components

Reusable primitives live in `apps/web/components/ui/`: `Card`, `Modal`, `Badge`, `Popover`,
`ProgressBar`, `ScoreRing`, `TrendPill`, `SectionHeader`. They consume tokens, not hex values —
extend them rather than writing one-off styled `div`s.

Marketing-only primitives (`apps/web/components/marketing/`): `MarketingNav`, `Hero`,
`FeatureGrid`, `FrameworkLogoStrip`, `FAQAccordion`, `CTASection` — scoped to `(marketing)`,
never imported from `(app)`.

## Icons & charts

- Icons: `lucide-react`, stroke width `1.75` (already the app-wide convention).
- Charts: hand-built, dependency-free SVG (see `ScoreRing`, `RiskDistribution`). Don't add a
  charting library unless a page genuinely needs interactive/animated trend data that's
  impractical by hand — flag it for discussion first.

## Technical-detail guardrail

No UI copy, label, tooltip, or citation may reference: model names (GPT, Claude, etc.), vendor
names (OpenAI, Anthropic), embedding dimensions, vector/chunk IDs, or other internal
implementation details. Citations show **source document name + section** only. This applies to
every surface — chat responses, analysis findings, report exports, error messages. Enforced by
code review, not a runtime check (see CLAUDE.md §19).

## Accessibility baseline

- All color pairings above are WCAG AA-checked for text-on-background use; if you introduce a
  new pairing, verify contrast before shipping.
- Every interactive element needs a visible focus ring, a keyboard path, and (where it's not
  self-evident from visible text) an `aria-label`.
- Don't rely on color alone for status — pair every status color with an icon or text label.
