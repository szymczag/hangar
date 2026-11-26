/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * A workspace slug as it may go into an API path. Django's `SlugField` takes
 * `[-a-zA-Z0-9_]`, but workspaces created before that rule was enforced kept
 * slugs with other characters (some hold dots), so this refuses only what could
 * change the path or query: `/`, `\`, `?`, `#`, `%`, control characters, and a
 * bare `.` or `..`. Callers still encode the slug.
 */
export const WORKSPACE_SLUG_PATTERN = /^(?!\.{1,2}$)[^/\\?#%\p{Cc}]+$/u;

/** A canonical UUID, the form of every project and page id. */
export const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export const isWorkspaceSlug = (value: unknown): value is string =>
  typeof value === "string" && WORKSPACE_SLUG_PATTERN.test(value);

export const isUuid = (value: unknown): value is string => typeof value === "string" && UUID_PATTERN.test(value);
