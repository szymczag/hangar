// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

// Minimal, strict reader for npm package tarballs (gzip-compressed ustar).
// It accepts regular files and directories only, applies PAX `path` records,
// and refuses links, devices, absolute paths and `..` segments, so a hostile
// archive cannot write outside the in-memory file map it returns.

import { createHash } from "node:crypto";
import { posix } from "node:path";
import { gunzipSync } from "node:zlib";

const BLOCK = 512;

export class RecoveryError extends Error {
  constructor(message) {
    super(message);
    this.name = "RecoveryError";
  }
}

export function sriSha512(buffer) {
  return `sha512-${createHash("sha512").update(buffer).digest("base64")}`;
}

export function sha256Hex(buffer) {
  return createHash("sha256").update(buffer).digest("hex");
}

export function verifyIntegrity(buffer, expected) {
  if (typeof expected !== "string" || !/^sha512-[A-Za-z0-9+/]+={0,2}$/.test(expected)) {
    throw new RecoveryError(`expected integrity must be an SRI sha512 value, got ${JSON.stringify(expected)}`);
  }
  const actual = sriSha512(buffer);
  if (actual !== expected) {
    throw new RecoveryError(`tarball integrity mismatch: expected ${expected}, got ${actual}`);
  }
}

function readString(block, offset, length) {
  const end = block.indexOf(0, offset);
  const stop = end === -1 || end > offset + length ? offset + length : end;
  return block.toString("utf8", offset, stop);
}

function readOctal(block, offset, length) {
  const text = readString(block, offset, length).trim();
  if (text === "") return 0;
  if (!/^[0-7]+$/.test(text)) throw new RecoveryError(`invalid octal field in tar header: ${JSON.stringify(text)}`);
  return Number.parseInt(text, 8);
}

function parsePax(buffer) {
  const records = {};
  let offset = 0;
  while (offset < buffer.length) {
    const space = buffer.indexOf(0x20, offset);
    if (space === -1) throw new RecoveryError("malformed PAX header");
    const length = Number.parseInt(buffer.toString("utf8", offset, space), 10);
    if (!Number.isInteger(length) || length <= 0) throw new RecoveryError("malformed PAX record length");
    const record = buffer.toString("utf8", space + 1, offset + length - 1);
    const equals = record.indexOf("=");
    if (equals === -1) throw new RecoveryError("malformed PAX record");
    records[record.slice(0, equals)] = record.slice(equals + 1);
    offset += length;
  }
  return records;
}

function safePath(raw) {
  if (raw.startsWith("/") || raw.includes("\\") || raw.includes("\0")) {
    throw new RecoveryError(`unsafe path in tarball: ${JSON.stringify(raw)}`);
  }
  const normalized = posix.normalize(raw);
  if (normalized.split("/").includes("..")) {
    throw new RecoveryError(`unsafe path in tarball: ${JSON.stringify(raw)}`);
  }
  return normalized.replace(/\/$/, "");
}

/**
 * Read a gzip-compressed npm tarball into a Map of `path -> Buffer`, with the
 * leading `package/` directory stripped.
 */
export function readPackageTarball(gzipped) {
  const tar = gunzipSync(gzipped);
  const files = new Map();
  let offset = 0;
  let pending = {};
  while (offset + BLOCK <= tar.length) {
    const header = tar.subarray(offset, offset + BLOCK);
    if (header.every((byte) => byte === 0)) break;

    const checksum = readOctal(header, 148, 8);
    let sum = 0;
    for (let index = 0; index < BLOCK; index += 1) sum += index >= 148 && index < 156 ? 0x20 : header[index];
    if (sum !== checksum) throw new RecoveryError(`tar header checksum mismatch at offset ${offset}`);

    const size = readOctal(header, 124, 12);
    const type = String.fromCharCode(header[156] || 0x30);
    const magic = header.toString("utf8", 257, 262);
    const prefix = magic === "ustar" ? readString(header, 345, 155) : "";
    const name = readString(header, 0, 100);
    const body = tar.subarray(offset + BLOCK, offset + BLOCK + size);
    if (body.length !== size) throw new RecoveryError("truncated tarball");
    offset += BLOCK + Math.ceil(size / BLOCK) * BLOCK;

    if (type === "x") {
      pending = parsePax(body);
      continue;
    }
    if (type === "g") continue;

    const rawPath = pending.path ?? (prefix ? `${prefix}/${name}` : name);
    pending = {};
    if (type === "5") continue;
    if (type !== "0") throw new RecoveryError(`unsupported tar entry type ${JSON.stringify(type)} for ${rawPath}`);

    const path = safePath(rawPath);
    if (!path.startsWith("package/")) throw new RecoveryError(`tar entry outside package/: ${path}`);
    const relative = path.slice("package/".length);
    if (files.has(relative)) throw new RecoveryError(`duplicate tar entry: ${relative}`);
    files.set(relative, Buffer.from(body));
  }
  return files;
}
