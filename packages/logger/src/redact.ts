/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { Logform } from "winston";
import { format } from "winston";

export const REDACTED = "[REDACTED]";

const MAX_DEPTH = 10;

/** Most objects and array items one log entry may visit; anything beyond is written as `[Truncated]`. */
export const MAX_NODES = 5000;

/**
 * Header names whose values are credentials. Matched case-insensitively, both as object keys and as
 * `Name: value` text anywhere in a string (such as the `_header` of a Node request inside an axios error).
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
 * Whether a property or parameter name holds a credential: a sensitive header, a cookie, a CSRF or session value,
 * a signature or credential (`X-Amz-Signature`, `X-Amz-Credential`), or any name ending in token, secret, password
 * or API key.
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
    normalised.includes("credential") ||
    normalised.endsWith("signature") ||
    normalised.endsWith("token") ||
    normalised.endsWith("secret") ||
    normalised.endsWith("secretkey") ||
    normalised.endsWith("password") ||
    normalised.endsWith("apikey")
  );
};

const decodeName = (name: string): string => {
  if (!name.includes("%")) return name;
  try {
    return decodeURIComponent(name);
  } catch {
    return name;
  }
};

const escapeRegExp = (value: string): string => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

const HEADER_NAME_PATTERN = SENSITIVE_HEADER_NAMES.map(escapeRegExp).join("|");

// Every pattern below is linear: each quantified class is followed by a character it cannot match, and patterns
// that could start inside a run of word characters are anchored by a lookbehind, so no input makes them backtrack
// over the same text twice. redact.test.ts times them on 200 KB adversarial inputs.

// `Cookie: a=b` anywhere in a string, quoted or not. The whole rest of the line is the value, whatever the cookie
// names are (the session cookie name is configurable). The line ends at a real CR/LF or at a backslash, which is
// where JSON-escaped header text (`\r\n`) continues.
const HEADER_TEXT = new RegExp(
  `(?:(?<![\\w-])|(?<=\\\\[rnt]))(${HEADER_NAME_PATTERN})(["']?[ \\t]*:[ \\t]*)[^\\r\\n\\\\]*`,
  "gi"
);

// `"name": "value"`, `'name': 'value'` (util.inspect) and `name: 'value'` pairs; redacted when the name is sensitive.
const QUOTED_PAIR = /(["'])([\w.$-]+)\1(\s*:\s*)(["'`])(?:(?!\4)[^\\]|\\.)*\4/g;
const BARE_KEY_PAIR = /(?<![\w$.-])([A-Za-z_$][\w$]*)(\s*:\s*)(["'`])(?:(?!\3)[^\\]|\\.)*\3/g;

// `cookie=...` in free text: everything up to the end of the line, a query separator or a quote.
const COOKIE_ASSIGNMENT = /(?<![\w-])(cookies?)=[^\r\n\\&"']*/gi;

// `name=value` pairs in cookie strings and query strings; the name may be percent-encoded (`%74oken=`).
const ASSIGNMENT = /(^|[\s?&;,"'(])([\w.%-]+)=([^\s&;,"')]*)/g;

// Authorization schemes. `Token` needs a token-shaped value, so prose such as "Token parsing failed" is kept.
const AUTH_SCHEME = /(?<![\w-])(bearer|basic|digest|negotiate)(\s+)[A-Za-z0-9._~+/=-]+/gi;
const TOKEN_SCHEME = /(?<![\w-])(token)(\s+)[A-Za-z0-9._~+/=-]{16,}/gi;

// `scheme://user:password@host`.
const URL_USERINFO = /(?<![a-z0-9+.-])([a-z][a-z0-9+.-]*:\/\/)[^\s/?#@"'<>\\]+@/gi;

/**
 * Removes credential values from free text: sensitive header text anywhere in a line (raw or JSON-escaped),
 * sensitive JSON and util.inspect pairs, `cookie=` text, sensitive `name=value` pairs, authorization schemes and
 * URL userinfo.
 */
export const redactString = (value: string): string => {
  if (value.length === 0) return value;
  return value
    .replace(HEADER_TEXT, `$1$2${REDACTED}`)
    .replace(QUOTED_PAIR, (match, quote: string, name: string, separator: string, valueQuote: string) =>
      isSensitiveKey(name) ? `${quote}${name}${quote}${separator}${valueQuote}${REDACTED}${valueQuote}` : match
    )
    .replace(BARE_KEY_PAIR, (match, name: string, separator: string, valueQuote: string) =>
      isSensitiveKey(name) ? `${name}${separator}${valueQuote}${REDACTED}${valueQuote}` : match
    )
    .replace(URL_USERINFO, `$1${REDACTED}@`)
    .replace(AUTH_SCHEME, `$1$2${REDACTED}`)
    .replace(TOKEN_SCHEME, `$1$2${REDACTED}`)
    .replace(COOKIE_ASSIGNMENT, `$1=${REDACTED}`)
    .replace(ASSIGNMENT, (match, prefix: string, name: string, assigned: string) =>
      assigned !== REDACTED && isSensitiveKey(decodeName(name)) ? `${prefix}${name}=${REDACTED}` : match
    );
};

const binaryPlaceholder = (value: object): string | undefined => {
  if (typeof Buffer !== "undefined" && Buffer.isBuffer(value)) return `[Buffer ${value.length} bytes]`;
  if (ArrayBuffer.isView(value)) return `[${value.constructor.name} ${value.byteLength} bytes]`;
  if (value instanceof ArrayBuffer) return `[ArrayBuffer ${value.byteLength} bytes]`;
  return undefined;
};

type WalkState = {
  /** Objects on the current path; meeting one again is a cycle. */
  ancestors: WeakSet<object>;
  /** Redacted copies of objects already walked, reused when a structure shares them. */
  done: WeakMap<object, unknown>;
  nodes: number;
};

const redactNode = (value: unknown, depth: number, state: WalkState): unknown => {
  if (typeof value === "string") return redactString(value);
  if (value === null || typeof value !== "object") return value;
  if (value instanceof Date) return value;
  const binary = binaryPlaceholder(value);
  if (binary) return binary;
  if (state.ancestors.has(value)) return "[Circular]";
  if (state.done.has(value)) return state.done.get(value);
  if (depth >= MAX_DEPTH || state.nodes >= MAX_NODES) return "[Truncated]";
  state.nodes += 1;
  state.ancestors.add(value);

  try {
    let output: unknown;
    if (Array.isArray(value)) {
      // A flat name/value list (Node's `req.rawHeaders`) puts the header value in the item after its name.
      output = value.map((item, index) => {
        const previous: unknown = index > 0 ? value[index - 1] : undefined;
        if (typeof previous === "string" && SENSITIVE_KEYS.has(normaliseKey(previous))) return REDACTED;
        return redactNode(item, depth + 1, state);
      });
    } else {
      const source = value as Record<string, unknown>;
      const copy: Record<string, unknown> = {};
      let fromJson = false;

      if (value instanceof Error) {
        copy.name = value.name;
        copy.message = redactString(value.message);
        if (value.stack) copy.stack = redactString(value.stack);
      } else if (typeof source.toJSON === "function") {
        // Serialisers call toJSON; redact what it returns rather than the instance's internals.
        fromJson = true;
        try {
          output = redactNode(source.toJSON(), depth + 1, state);
        } catch {
          output = "[Unserialisable]";
        }
      }

      if (!fromJson) {
        for (const key of Object.keys(source)) {
          copy[key] = isSensitiveKey(key) ? REDACTED : redactNode(source[key], depth + 1, state);
        }
        output = copy;
      }
    }
    state.done.set(value, output);
    return output;
  } finally {
    state.ancestors.delete(value);
  }
};

const newState = (): WalkState => ({ ancestors: new WeakSet(), done: new WeakMap(), nodes: 0 });

/**
 * Returns a copy of a value with credentials removed: values under sensitive keys are replaced, binary data is
 * replaced by its size, and strings are scrubbed as `redactString` does. The input is never modified, so objects the
 * application still uses (an axios config, a request) keep their headers.
 */
export const redactSensitiveData = <T>(value: T): T => redactNode(value, 0, newState()) as T;

/**
 * Winston format that redacts every log entry. Symbol-keyed values are redacted too: `Symbol.for("splat")` holds the
 * raw arguments that `format.splat()` would merge back into the entry, and `Symbol.for("message")` the output of any
 * format that ran earlier, so the entry stays clean whatever order formats are combined in.
 */
export const redactFormat: Logform.FormatWrap = format((info) => {
  const state = newState();
  state.ancestors.add(info);
  const output: Record<string | symbol, unknown> = {};
  for (const key of Reflect.ownKeys(info)) {
    const value = (info as Record<string | symbol, unknown>)[key];
    output[key] = typeof key === "string" && isSensitiveKey(key) ? REDACTED : redactNode(value, 1, state);
  }
  return output as typeof info;
});
