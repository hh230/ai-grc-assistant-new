"use client";

import { useSyncExternalStore } from "react";

function safeParse<T>(raw: string | null, fallback: T): T {
  if (!raw) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

/**
 * A small localStorage-backed, most-recent-first list store, shared by recent searches,
 * recently-viewed items, and favorites (V2-P3 Milestone 6). Client-only, per-browser
 * persistence — a genuine, working feature, not a stand-in for a backend: there is no
 * `saved_items`/`search_history` Tool or table yet (flagged as future scope in the V2-P3
 * design proposal §9/§10), so this is the honest frontend-only version of "remember this
 * for me," scoped to the current browser rather than synced across devices.
 */
export function createLocalListStore<T>(options: {
  storageKey: string;
  maxItems: number;
  itemKey: (item: T) => string;
}) {
  const { storageKey, maxItems, itemKey } = options;
  const listeners = new Set<() => void>();
  const emptySnapshot: T[] = [];

  // `useSyncExternalStore` requires `getSnapshot` to return a referentially stable value
  // when nothing has changed — re-parsing localStorage on every call would hand back a new
  // array each time and trip React's "getSnapshot should be cached" infinite-loop guard.
  // `cache` is that stable snapshot; it's only replaced (once) inside `write`.
  let cache: T[] | null = null;

  function readFromStorage(): T[] {
    if (typeof window === "undefined") return emptySnapshot;
    return safeParse<T[]>(window.localStorage.getItem(storageKey), emptySnapshot);
  }

  /** The current list. Safe to call anytime; does not re-read storage once cached. */
  function read(): T[] {
    if (cache === null) cache = readFromStorage();
    return cache;
  }

  function write(items: T[]) {
    cache = items;
    if (typeof window !== "undefined") {
      window.localStorage.setItem(storageKey, JSON.stringify(items));
    }
    listeners.forEach((listener) => listener());
  }

  function subscribe(listener: () => void) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  }

  function add(item: T) {
    const key = itemKey(item);
    const existing = read().filter((i) => itemKey(i) !== key);
    write([item, ...existing].slice(0, maxItems));
  }

  function remove(key: string) {
    write(read().filter((i) => itemKey(i) !== key));
  }

  function clear() {
    write(emptySnapshot);
  }

  function useItems(): T[] {
    return useSyncExternalStore(subscribe, read, () => emptySnapshot);
  }

  return { add, remove, clear, read, useItems };
}
