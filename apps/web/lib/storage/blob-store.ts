/**
 * Blob storage behind a port — the seam for object storage. Local filesystem under
 * `STORAGE_DIR` for dev (Vercel's serverless functions have a read-only filesystem, so this
 * adapter cannot back production); Vercel Blob when `BLOB_READ_WRITE_TOKEN` is configured
 * (CLAUDE.md §6 #5, §17). Same interface either way — callers never touch either provider
 * directly. Node-only.
 */

import { createHash } from "node:crypto";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { del, put, get as blobGet } from "@vercel/blob";

export interface BlobStore {
  put(key: string, data: Buffer): Promise<void>;
  get(key: string): Promise<Buffer>;
  delete(key: string): Promise<void>;
}

/** Root directory for all uploaded artifacts. Configurable; defaults under the app cwd. */
export function storageRoot(): string {
  return process.env.STORAGE_DIR ?? path.join(process.cwd(), ".data");
}

class FileSystemBlobStore implements BlobStore {
  private readonly blobsDir = path.join(storageRoot(), "blobs");

  private resolve(key: string): string {
    // Defend against path traversal: keys are opaque ids, never user-supplied paths.
    const safe = path.normalize(key).replace(/^(\.\.(\/|\\|$))+/, "");
    return path.join(this.blobsDir, safe);
  }

  async put(key: string, data: Buffer): Promise<void> {
    const target = this.resolve(key);
    await mkdir(path.dirname(target), { recursive: true });
    await writeFile(target, data);
  }

  async get(key: string): Promise<Buffer> {
    return readFile(this.resolve(key));
  }

  async delete(key: string): Promise<void> {
    await rm(this.resolve(key), { force: true });
  }
}

// Documents/evidence are private tenant data — never the 'public' access level, which
// serves blobs over an unauthenticated CDN URL.
const BLOB_ACCESS = "private" as const;

class VercelBlobStore implements BlobStore {
  async put(key: string, data: Buffer): Promise<void> {
    await put(key, data, { access: BLOB_ACCESS, addRandomSuffix: false, allowOverwrite: true });
  }

  async get(key: string): Promise<Buffer> {
    const result = await blobGet(key, { access: BLOB_ACCESS });
    if (!result) throw new Error(`Blob not found: ${key}`);
    return Buffer.from(await new Response(result.stream).arrayBuffer());
  }

  async delete(key: string): Promise<void> {
    await del(key);
  }
}

export const blobStore: BlobStore = process.env.BLOB_READ_WRITE_TOKEN
  ? new VercelBlobStore()
  : new FileSystemBlobStore();

/** Stable content-addressable storage key for a tenant's blob. */
export function makeStorageKey(tenantId: string, documentId: string): string {
  return `${tenantId}/${documentId}`;
}

export function sha256(data: Buffer): string {
  return createHash("sha256").update(data).digest("hex");
}
