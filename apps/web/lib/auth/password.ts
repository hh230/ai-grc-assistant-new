/**
 * Password hashing/verification using Node's built-in scrypt (no external dependency).
 * Node-only — import exclusively from route handlers / server code, never from middleware
 * (edge) or client components. Hash format: `scrypt$N$r$p$saltHex$hashHex`.
 */

import { randomBytes, scrypt as scryptCallback, timingSafeEqual } from "node:crypto";

const KEYLEN = 64;
const PARAMS = { N: 16384, r: 8, p: 1 } as const;

interface ScryptParams {
  N: number;
  r: number;
  p: number;
}

function scrypt(
  password: string,
  salt: Buffer,
  keylen: number,
  params: ScryptParams,
): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    scryptCallback(password, salt, keylen, params, (error, derivedKey) => {
      if (error) reject(error);
      else resolve(derivedKey);
    });
  });
}

export async function hashPassword(password: string): Promise<string> {
  const salt = randomBytes(16);
  const derived = await scrypt(password, salt, KEYLEN, PARAMS);
  return `scrypt$${PARAMS.N}$${PARAMS.r}$${PARAMS.p}$${salt.toString("hex")}$${derived.toString("hex")}`;
}

export async function verifyPassword(password: string, stored: string): Promise<boolean> {
  const parts = stored.split("$");
  if (parts.length !== 6 || parts[0] !== "scrypt") return false;
  const [, nRaw, rRaw, pRaw, saltHex, hashHex] = parts as [
    string,
    string,
    string,
    string,
    string,
    string,
  ];
  const params: ScryptParams = { N: Number(nRaw), r: Number(rRaw), p: Number(pRaw) };
  if (!params.N || !params.r || !params.p || !saltHex || !hashHex) return false;

  const salt = Buffer.from(saltHex, "hex");
  const expected = Buffer.from(hashHex, "hex");
  const derived = await scrypt(password, salt, expected.length, params);
  // Constant-time comparison to avoid leaking timing information.
  return derived.length === expected.length && timingSafeEqual(derived, expected);
}
