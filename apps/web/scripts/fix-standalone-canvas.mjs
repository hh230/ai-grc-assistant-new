#!/usr/bin/env node
/**
 * Patches two pnpm symlinks that Next's `outputFileTracingIncludes` glob copies as real
 * files but doesn't recreate as symlinks in `.next/standalone` (its glob doesn't traverse
 * existing symlinked directories the way pnpm's own linker does):
 *
 *   1. pdfjs-dist's own `@napi-rs/canvas` link (pnpm links every package's optional/regular
 *      deps as siblings inside `.pnpm/<pkg>@<version>/node_modules/`) — without it,
 *      pdfjs-dist's `require("@napi-rs/canvas")` can't resolve at all.
 *   2. @napi-rs/canvas's own link to its platform-specific native binding package (e.g.
 *      `@napi-rs/canvas-darwin-arm64`) — without it, the binding loads no native addon.
 *
 * Idempotent and a no-op if the standalone output or the packages aren't present (e.g. a
 * build that doesn't touch PDF analysis). Node-only, no dependencies.
 */

import { existsSync, readdirSync, symlinkSync, mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const appRoot = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const pnpmStore = path.join(appRoot, "..", "..", ".next", "standalone", "node_modules", ".pnpm");
// Nested build (apps/web/.next/standalone/...) is what pnpm workspaces actually produce.
const nestedPnpmStore = path.join(appRoot, ".next", "standalone", "node_modules", ".pnpm");

function findStore() {
  if (existsSync(nestedPnpmStore)) return nestedPnpmStore;
  if (existsSync(pnpmStore)) return pnpmStore;
  return null;
}

function findDirs(store, prefix) {
  return readdirSync(store)
    .filter((name) => name.startsWith(prefix))
    .map((name) => path.join(store, name));
}

function linkIfMissing(linkPath, target) {
  if (existsSync(linkPath)) return false;
  mkdirSync(path.dirname(linkPath), { recursive: true });
  const relativeTarget = path.relative(path.dirname(linkPath), target);
  symlinkSync(relativeTarget, linkPath, "dir");
  return true;
}

function main() {
  const store = findStore();
  if (!store) {
    console.log("fix-standalone-canvas: no standalone output, skipping.");
    return;
  }

  const canvasDirs = findDirs(store, "@napi-rs+canvas@");
  if (canvasDirs.length === 0) {
    console.log("fix-standalone-canvas: @napi-rs/canvas not in standalone output, skipping.");
    return;
  }
  const canvasRealDir = path.join(canvasDirs[0], "node_modules", "@napi-rs", "canvas");

  // 1. pdfjs-dist -> @napi-rs/canvas
  for (const pdfjsDir of findDirs(store, "pdfjs-dist@")) {
    const link = path.join(pdfjsDir, "node_modules", "@napi-rs", "canvas");
    if (linkIfMissing(link, canvasRealDir)) {
      console.log(`fix-standalone-canvas: linked ${link}`);
    }
  }

  // 2. @napi-rs/canvas -> its platform-specific native binding package.
  const platformDirs = findDirs(store, "@napi-rs+canvas-").filter((d) =>
    path.basename(d).startsWith("@napi-rs+canvas-"),
  );
  for (const platformDir of platformDirs) {
    const pkgName = path.basename(platformDir).split("@napi-rs+")[1].split("@")[0];
    const realDir = path.join(platformDir, "node_modules", "@napi-rs", pkgName);
    const link = path.join(canvasDirs[0], "node_modules", "@napi-rs", pkgName);
    if (linkIfMissing(link, realDir)) {
      console.log(`fix-standalone-canvas: linked ${link}`);
    }
  }
}

main();
