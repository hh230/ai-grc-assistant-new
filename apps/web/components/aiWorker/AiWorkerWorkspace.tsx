"use client";

import { ActivityTimeline } from "./ActivityTimeline";
import { LearningReportsCard } from "./LearningReportsCard";
import { ScheduleControl } from "./ScheduleControl";
import { TriggerButton } from "./TriggerButton";
import { WorkerStatusCard } from "./WorkerStatusCard";

export function AiWorkerWorkspace() {
  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <WorkerStatusCard />
        </div>
      </div>

      <div className="flex justify-end">
        <TriggerButton />
      </div>

      <ScheduleControl />

      <div className="grid grid-cols-12 gap-5">
        <div className="col-span-12 lg:col-span-7">
          <ActivityTimeline />
        </div>
        <div className="col-span-12 lg:col-span-5">
          <LearningReportsCard />
        </div>
      </div>
    </div>
  );
}
