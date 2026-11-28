/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { Logform } from "winston";
import { format } from "winston";

export const REDACTED = "[REDACTED]";

const MAX_DEPTH = 10;

/**
 * Header names whose values are credentials. Matched case-insensitively, both as object keys and as
 * `Name: value` lines in raw HTTP text (such as the `_header` string of a Node request inside an axios error).
 */
export const SENSITIVE_HEADER_NAMES: readonly string[] = [
  "cookie",
  "set-cookie",
  "authorization",
  "proxy-authorization",
  "x-api-key",
  "x-csrftoken",
  "x-csrf-token",
  "x-xsrf-token",
  "live-server-secret-key",
  "x-admin-secret-key",
];

const normaliseKey = (key: string): string => key.toLowerCase().replace(/[^a-z0-9]/g, "");

const SENSITIVE_KEYS = new Set(SENSITIVE_HEADER_NAMES.map(normaliseKey));

/**
 * Whether a property name holds a credential: a sensitive header, a cookie, a CSRF or session value, or any
 * name ending in token, secret, password or API key.
 */
export const isSensitiveKey = (key: string): boolean => {
  const normalised = normaliseKey(key);
  if (SENSITIVE_KEYS.has(normalised)) return true;
  return (
    normalised.includes("cookie") ||
    normalised.includes("authorization") ||
    normalised.includes("csrf") ||
    normalised.includes("xsrf") ||
    normalised.includes("sessionid") ||
    normalised.endsWith("token") ||
    normalised.endsWith("secret") ||
    normalised.endsWith("secretkey") ||
    normalised.endsWith("password") ||
    normalised.endsWith("apikey")
  );
};

const escapeRegExp = (value: string): string => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

const HEADER_NAME_PATTERN = SENSITIVE_HEADER_NAMES.map(escapeRegExp).join("|");

// `Cookie: a=b` lines in raw HTTP text. The value runs to the end of the line.
const RAW_HEADER_LINE = new RegExp(`(^|[\\r\\n])([ \\t]*(?:${HEADER_NAME_PATTERN})[ \\t]*:)[^\\r\\n]*`, "gi");

// `"name": "value"` inside serialised JSON, such as a collaboration token echoed into an error message.
const JSON_PAIR = /"([\w-]+)"(\s*:\s*)"(?:[^"\\]|\\.)*"/g;

// `name=value` pairs in cookie strings and query strings, such as `session-id=...; csrftoken=...` or `?token=...`.
const ASSIGNMENT = /(^|[\s?&;,"'(])([\w.-]+)=([^\s&;,"')]*)/g;

const AUTH_SCHEME = /\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]+/g;

/** Removes credential values from free text: raw header lines, JSON pairs, cookie or query pairs and auth schemes. */
export const redactString = (value: string): string => {
  if (value.length === 0) return value;
  return value
    .replace(RAW_HEADER_LINE, `$1$2 ${REDACTED}`)
    .replace(JSON_PAIR, (match, name: string, separator: string) =>
      isSensitiveKey(name) ? `"${name}"${separator}"${REDACTED}"` : match
    )
    .replace(ASSIGNMENT, (match, prefix: string, name: string) =>
      isSensitiveKey(name) ? `${prefix}${name}=${REDACTED}` : match
    )
    .replace(AUTH_SCHEME, `$1 ${REDACTED}`);
};

const isBinary = (value: object): boolean => ArrayBuffer.isView(value) || value instanceof ArrayBuffer;

const redactNode = (value: unknown, depth: number, seen: WeakSet<object>): unknown => {
  if (typeof value === "string") return redactString(value);
  if (value === null || typeof value !== "object") return value;
  if (value instanceof Date || isBinary(value)) return value;
  if (seen.has(value)) return "[Circular]";
  if (depth >= MAX_DEPTH) return "[Truncated]";
  seen.add(value);

  try {
    if (Array.isArray(value)) return value.map((item) => redactNode(item, depth + 1, seen));

    const source = value as Record<string, unknown>;
    const output: Record<string, unknown> = {};

    if (value instanceof Error) {
      output.name = value.name;
      output.message = redactString(value.message);
      if (value.stack) output.stack = redactString(value.stack);
    } else if (typeof source.toJSON === "function") {
      // Serialisers call toJSON; redact what it returns rather than the instance's internals.
      try {
        return redactNode(source.toJSON(), depth + 1, seen);
      } catch {
        return "[Unserialisable]";
      }
    }

    for (const key of Object.keys(source)) {
      output[key] = isSensitiveKey(key) ? REDACTED : redactNode(source[key], depth + 1, seen);
    }
    return output;
  } finally {
    seen.delete(value);
  }
};

/**
 * Returns a copy of a value with credentials removed: values under sensitive keys are replaced, and strings are
 * scrubbed of cookie, token and authorization text. The input is never modified, so objects the application still
 * uses (an axios config, a request) keep their headers.
 */
export const redactSensitiveData = <T>(value: T): T => redactNode(value, 0, new WeakSet()) as T;

/**
 * Winston format that redacts every log entry before it is serialised. Symbol keys (level, message and splat
 * bookkeeping) are carried over untouched.
 */
export const redactFormat: Logform.FormatWrap = format((info) => {
  const seen = new WeakSet<object>();
  seen.add(info);
  const output: Record<string | symbol, unknown> = {};
  for (const key of Reflect.ownKeys(info)) {
    const value = (info as Record<string | symbol, unknown>)[key];
    if (typeof key === "symbol") {
      output[key] = value;
    } else if (isSensitiveKey(key)) {
      output[key] = REDACTED;
    } else {
      output[key] = redactNode(value, 1, seen);
    }
  }
  return output as typeof info;
});
