"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

export interface FAQItem {
  question: string;
  answer: string;
}

interface FAQAccordionProps {
  items: FAQItem[];
}

export function FAQAccordion({ items }: FAQAccordionProps) {
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  return (
    <div className="divide-y divide-hairline rounded-2xl border border-hairline bg-surface shadow-soft">
      {items.map((item, index) => {
        const open = openIndex === index;
        return (
          <div key={item.question}>
            <button
              type="button"
              onClick={() => setOpenIndex(open ? null : index)}
              aria-expanded={open}
              className="flex w-full items-center justify-between gap-4 px-6 py-5 text-start"
            >
              <span className="text-sm font-medium text-foreground">{item.question}</span>
              <ChevronDown
                className={cn(
                  "h-4 w-4 shrink-0 text-foreground-muted transition-transform duration-200",
                  open && "rotate-180",
                )}
                strokeWidth={1.75}
              />
            </button>
            {open && (
              <p className="px-6 pb-5 text-sm leading-relaxed text-foreground-secondary">
                {item.answer}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
