"use client";

import { useState } from "react";
import { AccessRequestList } from "./AccessRequestList";
import { AccessRequestDetailPanel } from "./AccessRequestDetailPanel";
import type { AccessRequest } from "@/lib/accessRequests/types";

export function AccessRequestsWorkspace() {
  // Holds a snapshot of the selected request, not just its id: approving/rejecting
  // invalidates the pending-requests query, so a derived lookup would go stale the instant
  // the mutation succeeds — right when the admin still needs to see the new invite link.
  const [selected, setSelected] = useState<AccessRequest | null>(null);

  return (
    <div className="grid grid-cols-12 gap-5">
      <div className="col-span-12 lg:col-span-5">
        <AccessRequestList selectedId={selected?.id ?? null} onSelect={setSelected} />
      </div>
      <div className="col-span-12 lg:col-span-7">
        <AccessRequestDetailPanel request={selected} onClose={() => setSelected(null)} />
      </div>
    </div>
  );
}
