"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchLearningReports,
  fetchWorkerEvents,
  fetchWorkerRuns,
  fetchWorkerStatus,
  triggerRun,
  updateSchedule,
} from "@/lib/knowledgeWorker/client";
import type {
  LearningReports,
  ScheduleUpdate,
  WorkerEvent,
  WorkerRun,
  WorkerStatus,
} from "@/lib/knowledgeWorker/types";

const STATUS_REFETCH_INTERVAL_MS = 15_000;

export function useWorkerStatus() {
  return useQuery<WorkerStatus>({
    queryKey: ["knowledge-worker", "status"],
    queryFn: fetchWorkerStatus,
    refetchInterval: STATUS_REFETCH_INTERVAL_MS,
  });
}

export function useWorkerEvents(limit = 50) {
  return useQuery<WorkerEvent[]>({
    queryKey: ["knowledge-worker", "events", limit],
    queryFn: () => fetchWorkerEvents(limit),
    refetchInterval: STATUS_REFETCH_INTERVAL_MS,
  });
}

export function useWorkerRuns(limit = 20) {
  return useQuery<WorkerRun[]>({
    queryKey: ["knowledge-worker", "runs", limit],
    queryFn: () => fetchWorkerRuns(limit),
  });
}

export function useLearningReports() {
  return useQuery<LearningReports>({
    queryKey: ["knowledge-worker", "reports"],
    queryFn: fetchLearningReports,
    refetchInterval: STATUS_REFETCH_INTERVAL_MS,
  });
}

function useInvalidateWorkerQueries() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["knowledge-worker"] });
}

export function useUpdateWorkerSchedule() {
  const invalidate = useInvalidateWorkerQueries();
  return useMutation({
    mutationFn: (update: ScheduleUpdate) => updateSchedule(update),
    onSuccess: () => invalidate(),
  });
}

export function useTriggerWorkerRun() {
  const invalidate = useInvalidateWorkerQueries();
  return useMutation({
    mutationFn: () => triggerRun(),
    onSuccess: () => invalidate(),
  });
}
