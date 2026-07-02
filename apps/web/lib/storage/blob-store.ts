/**
 * Blob storage behind a port — the seam for object storage. The shipped adapter writes to
 * the local filesystem under `STORAGE_DIR`; a production deployment binds an S3/GCS adapter
 * implementing the same interface without touching callers (CLAUDE.md §6 #5, §17).
 * Node-only.
 */

import { createHash } from "node:crypto";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";

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

export const blobStore: BlobStore = new FileSystemBlobStore();

/** Stable content-addressable storage key for a tenant's blob. */
export function makeStorageKey(tenantId: string, documentId: string): string {
  return `${tenantId}/${documentId}`;
}

export function sha256(data: Buffer): string {
  return createHash("sha256").update(data).digest("hex");
}
