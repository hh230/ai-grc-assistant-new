import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface CardProps {
  children: ReactNode;
  className?: string;
  /** Adds a faint top-down grain highlight for elevated, premium surfaces. */
  grain?: boolean;
  /** Removes inner padding for cards that manage their own layout (tables, lists). */
  flush?: boolean;
}

export function Card({ children, className, grain = false, flush = false }: CardProps) {
  return (
    <section
      className={cn(
        "relative rounded-2xl border border-hairline bg-surface shadow-soft",
        grain && "bg-surface-grain",
        !flush && "p-5",
        className,
      )}
    >
      {children}
    </section>
  );
}
