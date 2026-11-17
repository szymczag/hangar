/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { redirect } from "react-router";
import { ensureTrailingSlash } from "./helper";

/**
 * Returns the path to redirect to when `requestUrl` lacks a trailing slash, or `null`
 * when it already has one (or is the root).
 *
 * Every in-app link is built with a trailing slash (`compat/next/link.tsx`), and the
 * sidebar and settings navigation compare against those slashed paths. A URL typed,
 * bookmarked or pasted without the slash therefore matches its route but highlights
 * nothing, so it is canonicalised once here instead of in every comparator.
 *
 * A router request never carries the fragment. When the browser is already on the
 * requested URL (a cold load), its hash is kept so `#comment-…` links survive the
 * redirect; during an in-app navigation the browser location is still the previous
 * page, so its hash is not borrowed.
 */
export function getTrailingSlashRedirect(requestUrl: string, currentHref?: string): string | null {
  const request = new URL(requestUrl);
  const canonical = new URL(ensureTrailingSlash(requestUrl));
  if (canonical.pathname === request.pathname) return null;

  let hash = "";
  if (currentHref) {
    try {
      const current = new URL(currentHref);
      if (
        current.origin === request.origin &&
        current.pathname === request.pathname &&
        current.search === request.search
      ) {
        hash = current.hash;
      }
    } catch {
      // An unparsable location only costs the fragment.
    }
  }
  return `${canonical.pathname}${canonical.search}${hash}`;
}

/**
 * Client middleware that 308-redirects any navigation to a path without a trailing
 * slash to the slashed path (upstream makeplane/plane#9824). Generic over the result of
 * `next` so it fits both a route module's `clientMiddleware` and a data router's
 * `middleware`.
 */
export async function trailingSlashRedirectMiddleware<Result>(
  { request }: { request: Request },
  next: () => Promise<Result>
): Promise<Result> {
  const currentHref = typeof window === "undefined" ? undefined : window.location.href;
  const target = getTrailingSlashRedirect(request.url, currentHref);
  if (target !== null) {
    throw redirect(target, { status: 308 });
  }
  return next();
}
