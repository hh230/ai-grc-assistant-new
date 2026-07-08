#!/usr/bin/env node
/**
 * Patches two pnpm links that Next's `outputFileTracingIncludes` glob copies as real files
 * but doesn't recreate as symlinks in `.next/standalone` (its glob doesn't traverse existing
 * symlinked directories the way pnpm's own linker does):
 *
 *   1. pdfjs-dist's own `@napi-rs/canvas` link (pnpm links every package's optional/regular
 *      deps as siblings inside `.pnpm/<pkg>@<version>/node_modules/`) — without it,
 *      pdfjs-dist's `require("@napi-rs/canvas")` can't resolve at all.
 *   2. @napi-rs/canvas's own link to its platform-specific native binding package (e.g.
 *      `@napi-rs/canvas-darwin-arm64`) — without it, the binding loads no native addon.
 *
 * Recreates them as real directory copies, not symlinks: this build output gets zipped and
 * redistributed across Vercel's deployment/regional infrastructure, and symlinks aren't
 * guaranteed to survive that repackaging the way they survive a plain local `next build`
 * (confirmed missing in production after passing every local standalone-server test).
 *
 * Idempotent and a no-op if the standalone output or the packages aren't present (e.g. a
 * build that doesn't touch PDF analysis). Node-only, no dependencies.
 */

import { existsSync, readdirSync, cpSync, mkdirSync } from "node:fs";
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

function linkIfMissing(destPath, target) {
  if (existsSync(destPath)) return false;
  mkdirSync(path.dirname(destPath), { recursive: true });
  cpSync(target, destPath, { recursive: true, dereference: true });
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
  const canvasNapiRsDir = path.join(canvasDirs[0], "node_modules", "@napi-rs");

  // 1. @napi-rs/canvas -> its platform-specific native binding package, as a sibling inside
  // @napi-rs/canvas's OWN node_modules. Must happen before step 2, which copies this whole
  // directory (canvas + its now-fixed-up binding sibling) as one unit — unlike a symlink,
  // a plain directory copy doesn't transitively pick up a sibling fixed up afterwards.
  const platformDirs = findDirs(store, "@napi-rs+canvas-").filter((d) =>
    path.basename(d).startsWith("@napi-rs+canvas-"),
  );
  for (const platformDir of platformDirs) {
    const pkgName = path.basename(platformDir).split("@napi-rs+")[1].split("@")[0];
    const realDir = path.join(platformDir, "node_modules", "@napi-rs", pkgName);
    const dest = path.join(canvasNapiRsDir, pkgName);
    if (linkIfMissing(dest, realDir)) {
      console.log(`fix-standalone-canvas: copied ${dest}`);
    }
  }

  // 2. pdfjs-dist -> @napi-rs/canvas (+ its now-bundled platform binding from step 1).
  for (const pdfjsDir of findDirs(store, "pdfjs-dist@")) {
    const dest = path.join(pdfjsDir, "node_modules", "@napi-rs", "canvas");
    if (linkIfMissing(dest, path.join(canvasNapiRsDir, "canvas"))) {
      console.log(`fix-standalone-canvas: copied ${dest}`);
    }
    // The platform binding also needs to exist as pdfjs-dist's OWN sibling: @napi-rs/canvas's
    // require("@napi-rs/canvas-<platform>") resolves from wherever canvas physically sits,
    // and this copy of canvas is a separate directory tree from the original.
    for (const platformDir of platformDirs) {
      const pkgName = path.basename(platformDir).split("@napi-rs+")[1].split("@")[0];
      const realDir = path.join(platformDir, "node_modules", "@napi-rs", pkgName);
      const dest2 = path.join(pdfjsDir, "node_modules", "@napi-rs", pkgName);
      if (linkIfMissing(dest2, realDir)) {
        console.log(`fix-standalone-canvas: copied ${dest2}`);
      }
    }
  }
}

main();
