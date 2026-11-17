/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * Ensures an API request URL has a trailing slash on its path component, preserving
 * the query string and hash. Required by the Django backend's `APPEND_SLASH` behavior
 * — under Kubernetes ingress, requests without a trailing slash can fail instead of
 * 301-redirecting. Intended to be applied by an axios request interceptor so callers
 * do not need to remember to add the slash.
 *
 * Examples:
 *   "/api/foo"             -> "/api/foo/"
 *   "/api/foo/"            -> "/api/foo/"
 *   "/api/foo?x=1"         -> "/api/foo/?x=1"
 *   "/api/foo#frag"        -> "/api/foo/#frag"
 *   "https://h/api/foo"    -> "https://h/api/foo/"
 *   "" | "/"               -> unchanged
 */
export function ensureAPITrailingSlash(url: string): string {
  if (!url) return url;
  const boundary = url.search(/[?#]/);
  const path = boundary === -1 ? url : url.slice(0, boundary);
  const suffix = boundary === -1 ? "" : url.slice(boundary);
  if (!path || path.endsWith("/")) return url;
  return `${path}/${suffix}`;
}

/**
 * Same as `ensureAPITrailingSlash`, but only for requests to this instance's Django API.
 *
 * Left unchanged:
 * - absolute (and protocol-relative) URLs whose origin is not the API `baseURL`. Signed
 *   S3/GCS upload URLs go through `APIService` with an empty `baseURL`; slashing them
 *   invalidates the signature and 403s the upload.
 * - non-HTTP URLs such as `blob:` and `data:`.
 * - URLs that carry a request signature in the query string, whatever their origin
 *   (Hangar fork: MinIO can be served from the same origin as the API).
 * - paths whose last segment looks like a file name (`robots.txt`, `logo.png`). Every
 *   Django API route ends with a slash; a file-like path is not one of them.
 */
export function normalizeAPIRequestURL(url: string, baseURL: string): string {
  if (!url) return url;
  if (isForeignAbsoluteURL(url, baseURL)) return url;
  if (hasRequestSignature(url)) return url;
  if (hasFileLikeLastSegment(url)) return url;
  return ensureAPITrailingSlash(url);
}

function isForeignAbsoluteURL(url: string, baseURL: string): boolean {
  // Protocol-relative URLs name a host just like absolute ones.
  const isProtocolRelative = url.startsWith("//");
  let requestUrl: URL;
  try {
    requestUrl = new URL(isProtocolRelative ? `http:${url}` : url);
  } catch {
    // Not absolute: a path resolved against the API baseURL.
    return false;
  }
  if (requestUrl.protocol !== "http:" && requestUrl.protocol !== "https:") return true;
  if (!baseURL) return true;
  try {
    const base = new URL(baseURL);
    if (isProtocolRelative) return requestUrl.host !== base.host;
    return requestUrl.origin !== base.origin;
  } catch {
    return true;
  }
}

const SIGNATURE_QUERY_PARAMS = new Set(["x-amz-signature", "x-amz-credential", "x-goog-signature", "signature"]);

function hasRequestSignature(url: string): boolean {
  const queryStart = url.indexOf("?");
  if (queryStart === -1) return false;
  const hashStart = url.indexOf("#", queryStart);
  const query = url.slice(queryStart + 1, hashStart === -1 ? undefined : hashStart);
  return query.split("&").some((pair) => SIGNATURE_QUERY_PARAMS.has(pair.split("=")[0]?.toLowerCase() ?? ""));
}

function hasFileLikeLastSegment(url: string): boolean {
  const boundary = url.search(/[?#]/);
  const path = boundary === -1 ? url : url.slice(0, boundary);
  const lastSegment = path.slice(path.lastIndexOf("/") + 1);
  return /\.[a-z0-9]{1,8}$/i.test(lastSegment);
}
