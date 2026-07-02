import type { LucideIcon } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/utils";

export interface FeatureItem {
  icon: LucideIcon;
  title: string;
  description: string;
}

interface FeatureGridProps {
  items: readonly FeatureItem[];
  columns?: 2 | 3;
  className?: string;
}

export function FeatureGrid({ items, columns = 3, className }: FeatureGridProps) {
  return (
    <div
      className={cn(
        "grid grid-cols-1 gap-5 sm:grid-cols-2",
        columns === 3 ? "lg:grid-cols-3" : "lg:grid-cols-2",
        className,
      )}
    >
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <Card key={item.title} className="p-8">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-hairline-strong bg-surface-2 shadow-soft">
              <Icon className="h-5 w-5 text-accent" strokeWidth={1.75} />
            </div>
            <h3 className="mt-5 text-base font-semibold tracking-tight text-foreground">
              {item.title}
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-foreground-secondary">
              {item.description}
            </p>
          </Card>
        );
      })}
    </div>
  );
}
