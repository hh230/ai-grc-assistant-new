"use client";

import { useState } from "react";
import { PendingRegulationList } from "./PendingRegulationList";
import { RegulationVersionDetailPanel } from "./RegulationVersionDetailPanel";

export function RegulationReviewWorkspace() {
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null);

  return (
    <div className="grid grid-cols-12 gap-5">
      <div className="col-span-12 lg:col-span-5">
        <PendingRegulationList
          selectedVersionId={selectedVersionId}
          onSelect={setSelectedVersionId}
        />
      </div>
      <div className="col-span-12 lg:col-span-7">
        <RegulationVersionDetailPanel
          versionId={selectedVersionId}
          onDecided={() => setSelectedVersionId(null)}
        />
      </div>
    </div>
  );
}
