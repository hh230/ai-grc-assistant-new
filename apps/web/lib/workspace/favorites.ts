"use client";

import { createLocalListStore } from "./localListStore";
import type { SearchEntityType } from "@/lib/search/types";

export interface FavoriteItem {
  id: string;
  type: SearchEntityType;
  title: string;
  subtitle?: string;
  href: string;
  savedAt: string;
}

const store = createLocalListStore<FavoriteItem>({
  storageKey: "sentinel-grc:favorites",
  maxItems: 30,
  itemKey: (item) => `${item.type}:${item.id}`,
});

function keyOf(type: SearchEntityType, id: string): string {
  return `${type}:${id}`;
}

export function toggleFavorite(item: Omit<FavoriteItem, "savedAt">) {
  const key = keyOf(item.type, item.id);
  const isSaved = store.read().some((i) => keyOf(i.type, i.id) === key);
  if (isSaved) {
    store.remove(key);
  } else {
    store.add({ ...item, savedAt: new Date().toISOString() });
  }
}

export function useIsFavorite(type: SearchEntityType, id: string): boolean {
  const items = store.useItems();
  return items.some((item) => item.type === type && item.id === id);
}

export const useFavorites = store.useItems;
