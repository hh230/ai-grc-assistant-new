"use client";

import { createLocalListStore } from "@/lib/workspace/localListStore";

const store = createLocalListStore<string>({
  storageKey: "sentinel-grc:recent-searches",
  maxItems: 6,
  itemKey: (query) => query.toLowerCase(),
});

export function addRecentSearch(query: string) {
  const trimmed = query.trim();
  if (trimmed.length < 2) return;
  store.add(trimmed);
}

export function removeRecentSearch(query: string) {
  store.remove(query.toLowerCase());
}

export function clearRecentSearches() {
  store.clear();
}

export const useRecentSearches = store.useItems;
