import { CircleCheck, CircleMinus } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";

interface StrengthsWeaknessesProps {
  strengths: string[];
  weaknesses: string[];
}

export function StrengthsWeaknesses({ strengths, weaknesses }: StrengthsWeaknessesProps) {
  if (strengths.length === 0 && weaknesses.length === 0) return null;

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      {strengths.length > 0 && (
        <Card>
          <SectionHeader title="Strengths" description="What the document already does well" />
          <ul className="mt-3 space-y-2">
            {strengths.map((item, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-foreground-secondary">
                <CircleCheck className="mt-0.5 h-4 w-4 shrink-0 text-success" strokeWidth={1.75} />
                {item}
              </li>
            ))}
          </ul>
        </Card>
      )}
      {weaknesses.length > 0 && (
        <Card>
          <SectionHeader title="Weaknesses" description="Gaps or omissions found in the text" />
          <ul className="mt-3 space-y-2">
            {weaknesses.map((item, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-foreground-secondary">
                <CircleMinus className="mt-0.5 h-4 w-4 shrink-0 text-danger" strokeWidth={1.75} />
                {item}
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
