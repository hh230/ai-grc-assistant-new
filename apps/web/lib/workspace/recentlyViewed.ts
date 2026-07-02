"use client";

import { createLocalListStore } from "./localListStore";
import type { SearchEntityType } from "@/lib/search/types";

export interface RecentlyViewedItem {
  id: string;
  type: SearchEntityType;
  title: string;
  subtitle?: string;
  href: string;
  viewedAt: string;
}

const store = createLocalListStore<RecentlyViewedItem>({
  storageKey: "sentinel-grc:recently-viewed",
  maxItems: 8,
  itemKey: (item) => `${item.type}:${item.id}`,
});

/** Call from a detail view's mount effect to record "the user just opened this." */
export function recordVisit(item: Omit<RecentlyViewedItem, "viewedAt">) {
  store.add({ ...item, viewedAt: new Date().toISOString() });
}

export const useRecentlyViewed = store.useItems;
