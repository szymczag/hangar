/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { lookup } from "node:dns/promises";
import { request as httpRequest } from "node:http";
import { request as httpsRequest } from "node:https";
import { BlockList, isIP } from "node:net";
import { Readable } from "node:stream";
import type { IncomingHttpHeaders, IncomingMessage, RequestOptions } from "node:http";
import type { LookupAddress } from "node:dns";

export const MAX_PDF_IMAGE_BYTES = 10 * 1024 * 1024;
export const MAX_PDF_IMAGE_COUNT = 50;
export const MAX_PDF_IMAGE_REDIRECTS = 5;

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const WORKSPACE_SLUG_PATTERN = /^[a-zA-Z0-9_-]{1,255}$/;
const PDF_IMAGE_CONTENT_TYPES = new Set(["image/gif", "image/jpeg", "image/png", "image/webp"]);
const REDIRECT_STATUSES = new Set([301, 302, 303, 307, 308]);
const MAX_RESOLVED_ADDRESSES = 8;

const ipv4BlockList = new BlockList();
const ipv6BlockList = new BlockList();

for (const [network, prefix] of [
  ["0.0.0.0", 8],
  ["10.0.0.0", 8],
  ["100.64.0.0", 10],
  ["127.0.0.0", 8],
  ["169.254.0.0", 16],
  ["172.16.0.0", 12],
  ["192.0.0.0", 24],
  ["192.0.2.0", 24],
  ["192.88.99.0", 24],
  ["192.168.0.0", 16],
  ["198.18.0.0", 15],
  ["198.51.100.0", 24],
  ["203.0.113.0", 24],
  ["224.0.0.0", 4],
  ["240.0.0.0", 4],
] as const) {
  ipv4BlockList.addSubnet(network, prefix, "ipv4");
}

for (const [network, prefix] of [
  ["::", 3],
  ["::", 128],
  ["::1", 128],
  ["::ffff:0:0", 96],
  ["64:ff9b::", 96],
  ["64:ff9b:1::", 48],
  ["100::", 64],
  ["2001::", 23],
  ["2001:db8::", 32],
  ["2002::", 16],
  ["3fff::", 20],
  ["4000::", 2],
  ["8000::", 1],
  ["fc00::", 7],
  ["fe80::", 10],
  ["fec0::", 10],
  ["ff00::", 8],
] as const) {
  ipv6BlockList.addSubnet(network, prefix, "ipv6");
}

export const isAssetId = (value: string): boolean => UUID_PATTERN.test(value);

export const isValidAssetReference = (workspaceSlug: string, assetId: string, projectId?: string | null): boolean =>
  WORKSPACE_SLUG_PATTERN.test(workspaceSlug) && isAssetId(assetId) && (!projectId || UUID_PATTERN.test(projectId));

export const isSafeAssetUrl = (value: string): boolean => {
  try {
    const parsed = new URL(value);
    return (
      (parsed.protocol === "https:" || parsed.protocol === "http:") &&
      parsed.hostname.length > 0 &&
      parsed.username.length === 0 &&
      parsed.password.length === 0
    );
  } catch {
    return false;
  }
};

const normalizeHostname = (hostname: string): string => hostname.replace(/\.$/, "").toLowerCase();
const unbracketHostname = (hostname: string): string => hostname.replace(/^\[|\]$/g, "");

const isBlockedAddress = ({ address, family }: LookupAddress): boolean =>
  family === 4 ? ipv4BlockList.check(address, "ipv4") : ipv6BlockList.check(address, "ipv6");

export const resolveAndValidateAssetHost = async (
  hostname: string,
  allowedHosts: ReadonlySet<string> = new Set()
): Promise<LookupAddress[]> => {
  const normalizedHost = normalizeHostname(hostname);
  const trustedHost = allowedHosts.has(normalizedHost);
  const addresses = await lookup(hostname, { all: true, verbatim: true });

  if (addresses.length === 0 || addresses.length > MAX_RESOLVED_ADDRESSES) {
    throw new Error("Asset hostname returned an invalid number of addresses");
  }

  if (!trustedHost && addresses.some(isBlockedAddress)) {
    throw new Error("Access to private or special-purpose networks is not allowed");
  }

  return addresses.filter(
    (candidate, index) =>
      addresses.findIndex((address) => address.address === candidate.address && address.family === candidate.family) ===
      index
  );
};

const responseHeaders = (headers: IncomingHttpHeaders): Headers => {
  const result = new Headers();
  for (const [name, value] of Object.entries(headers)) {
    if (Array.isArray(value)) {
      for (const item of value) result.append(name, item);
    } else if (value !== undefined) {
      result.set(name, value);
    }
  }
  return result;
};

const toWebResponse = (response: IncomingMessage): Response => {
  const status = response.statusCode ?? 500;
  const hasBody = status !== 204 && status !== 205 && status !== 304;
  const body = hasBody ? (Readable.toWeb(response) as ReadableStream<Uint8Array>) : null;
  return new Response(body, {
    status,
    statusText: response.statusMessage,
    headers: responseHeaders(response.headers),
  });
};

type PinnedRequestOptions = RequestOptions & {
  rejectUnauthorized?: boolean;
  servername?: string;
};

const requestPinnedAddress = (
  target: URL,
  address: LookupAddress,
  signal: AbortSignal | undefined
): Promise<Response> =>
  new Promise((resolve, reject) => {
    const isHttps = target.protocol === "https:";
    const options: PinnedRequestOptions = {
      protocol: target.protocol,
      hostname: address.address,
      family: address.family,
      port: target.port || (isHttps ? 443 : 80),
      path: `${target.pathname}${target.search}`,
      method: "GET",
      headers: {
        Accept: "image/avif,image/webp,image/png,image/jpeg,image/gif;q=0.9,*/*;q=0.1",
        Host: target.host,
      },
      signal,
    };

    if (isHttps) {
      const originalHostname = unbracketHostname(target.hostname);
      if (isIP(originalHostname) === 0) options.servername = originalHostname;
      options.rejectUnauthorized = true;
    }

    const request = (isHttps ? httpsRequest : httpRequest)(options, (response) => resolve(toWebResponse(response)));
    request.once("error", reject);
    request.end();
  });

const fetchPinnedHop = async (
  target: URL,
  allowedHosts: ReadonlySet<string>,
  signal: AbortSignal | undefined
): Promise<Response> => {
  const addresses = await resolveAndValidateAssetHost(unbracketHostname(target.hostname), allowedHosts);
  let lastError: unknown;

  for (const address of addresses) {
    try {
      // Each attempt connects to the already validated IP literal. No second DNS
      // lookup can rebind the request between validation and socket creation.
      // oxlint-disable-next-line no-await-in-loop -- address fallback is intentionally serial
      return await requestPinnedAddress(target, address, signal);
    } catch (error) {
      if (signal?.aborted) throw error;
      lastError = error;
    }
  }

  throw lastError instanceof Error ? lastError : new Error("No validated asset address was reachable");
};

export type PinnedAssetFetchOptions = {
  allowedHosts?: ReadonlySet<string>;
  maxRedirects?: number;
  signal?: AbortSignal;
};

export const pinnedAssetFetch = async (value: string, options: PinnedAssetFetchOptions = {}): Promise<Response> => {
  const allowedHosts = options.allowedHosts ?? new Set<string>();
  const maxRedirects = options.maxRedirects ?? MAX_PDF_IMAGE_REDIRECTS;
  let target = new URL(value);

  for (let redirectCount = 0; ; redirectCount += 1) {
    if (!isSafeAssetUrl(target.toString())) {
      throw new Error("Only credential-free HTTP and HTTPS asset URLs are allowed");
    }

    // oxlint-disable-next-line no-await-in-loop -- every redirect is independently validated and pinned
    const response = await fetchPinnedHop(target, allowedHosts, options.signal);
    if (!REDIRECT_STATUSES.has(response.status)) return response;

    const location = response.headers.get("location");
    if (!location) return response;
    if (redirectCount >= maxRedirects) {
      // oxlint-disable-next-line no-await-in-loop -- the current hop must close before failing
      await response.body?.cancel();
      throw new Error("Asset URL exceeded the redirect limit");
    }

    // oxlint-disable-next-line no-await-in-loop -- the current hop must close before following the next
    await response.body?.cancel();
    target = new URL(location, target);
  }
};

export const readBoundedImageDataUri = (value: string): Buffer => {
  const match = /^data:(image\/(?:gif|jpeg|png|webp));base64,([a-zA-Z0-9+/]*={0,2})$/.exec(value);
  if (!match?.[2] || match[2].length % 4 !== 0) {
    throw new Error("Unsupported PDF image data URI");
  }

  const decoded = Buffer.from(match[2], "base64");
  if (decoded.length === 0 || decoded.length > MAX_PDF_IMAGE_BYTES) {
    throw new Error("PDF image data URI is empty or too large");
  }
  return decoded;
};

export const isSafePdfImageDataUri = (value: string): boolean => {
  try {
    readBoundedImageDataUri(value);
    return true;
  } catch {
    return false;
  }
};

export const readBoundedImageResponse = async (response: Response): Promise<Buffer> => {
  const contentType = response.headers.get("content-type")?.split(";", 1)[0]?.trim().toLowerCase();
  if (!contentType || !PDF_IMAGE_CONTENT_TYPES.has(contentType)) {
    throw new Error("Unsupported PDF image content type");
  }

  const declaredLength = response.headers.get("content-length");
  if (declaredLength !== null) {
    const parsedLength = Number(declaredLength);
    if (!Number.isSafeInteger(parsedLength) || parsedLength < 0 || parsedLength > MAX_PDF_IMAGE_BYTES) {
      throw new Error("PDF image response is too large");
    }
  }

  if (!response.body) {
    throw new Error("PDF image response has no body");
  }

  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      // A response stream must be consumed serially to enforce the running byte cap.
      // oxlint-disable-next-line no-await-in-loop
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > MAX_PDF_IMAGE_BYTES) {
        // oxlint-disable-next-line no-await-in-loop
        await reader.cancel("PDF image response is too large");
        throw new Error("PDF image response is too large");
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }

  return Buffer.concat(
    chunks.map((chunk) => Buffer.from(chunk)),
    size
  );
};
