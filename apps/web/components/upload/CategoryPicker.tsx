"use client";

import {
  ClipboardCheck,
  ClipboardList,
  FileSignature,
  FileText,
  FolderOpen,
  Landmark,
  ShieldHalf,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react";
import {
  DOCUMENT_CATEGORIES,
  DOCUMENT_CATEGORY_LABELS,
  type DocumentCategory,
} from "@/lib/documents/types";
import { cn } from "@/lib/utils";

const CATEGORY_ICONS: Record<DocumentCategory, LucideIcon> = {
  governance: Landmark,
  risk_register: TriangleAlert,
  policies: FileText,
  contracts: FileSignature,
  compliance: ClipboardCheck,
  internal_audit: ClipboardList,
  cybersecurity: ShieldHalf,
  other: FolderOpen,
};

interface CategoryPickerProps {
  value: DocumentCategory | null;
  onChange: (category: DocumentCategory) => void;
}

/** Required classification step (V2-P2.5) — single-select grid of the 8 document categories. */
export function CategoryPicker({ value, onChange }: CategoryPickerProps) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4" role="radiogroup" aria-label="Document category">
      {DOCUMENT_CATEGORIES.map((category) => {
        const Icon = CATEGORY_ICONS[category];
        const selected = value === category;
        return (
          <button
            key={category}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(category)}
            className={cn(
              "flex flex-col items-center gap-2.5 rounded-2xl border px-4 py-5 text-center transition-colors duration-150",
              selected
                ? "border-accent/40 bg-accent-soft shadow-soft"
                : "border-hairline bg-surface hover:border-hairline-strong hover:bg-surface-2",
            )}
          >
            <span
              className={cn(
                "flex h-10 w-10 items-center justify-center rounded-xl border",
                selected
                  ? "border-accent/30 bg-surface text-accent"
                  : "border-hairline-strong bg-surface-2 text-foreground-secondary",
              )}
            >
              <Icon className="h-[18px] w-[18px]" strokeWidth={1.75} />
            </span>
            <span
              className={cn(
                "text-sm font-medium",
                selected ? "text-accent-foreground" : "text-foreground",
              )}
            >
              {DOCUMENT_CATEGORY_LABELS[category]}
            </span>
          </button>
        );
      })}
    </div>
  );
}
