/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { IWorkspace } from "@plane/types";

// Guest, matching DEFAULT_MINIMUM_ROLE in plane/utils/api_token_policy.py. Used
// only when the instance has not reported its own threshold; guessing higher
// would hide a feature that works, and the server refuses either way.
const DEFAULT_MINIMUM_ROLE = 5;

/**
 * The workspaces this account may mint an API token in.
 *
 * A token names the workspace it acts in and minting one needs a sufficient role
 * there, so the choice offered has to be the workspaces that qualify — not every
 * workspace the account belongs to. Offering the rest produces a form that is
 * accepted, filled in, and then refused.
 *
 * The server decides regardless; this only keeps the interface from proposing
 * what it will turn down.
 */
export const workspacesAllowingApiTokens = (
  workspaces: Record<string, IWorkspace> | IWorkspace[] | undefined,
  minimumRole: number | undefined
): IWorkspace[] => {
  const threshold = typeof minimumRole === "number" ? minimumRole : DEFAULT_MINIMUM_ROLE;
  const all = Array.isArray(workspaces) ? workspaces : Object.values(workspaces ?? {});
  // A workspace whose role is missing is left in: the account is a member, the
  // list simply did not say what it is, and the server will answer properly.
  return all.filter((workspace) => typeof workspace?.role !== "number" || workspace.role >= threshold);
};
