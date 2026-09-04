/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { readFileSync } from "node:fs";

export type VisualFixtures = {
  /** The instant everything seeded is anchored to, and the clock the browser is given. */
  clock: string;
  workspace: { slug: string; id: string };
  project: { id: string; identifier: string };
  copyTarget: { id: string };
  /** Names of the seeded work items, in the order they were created. */
  workItems: string[];
  users: Record<string, { email: string; sessionCookie?: string; adminSessionCookie?: string }>;
};

let cached: VisualFixtures | undefined;

/**
 * What the seed created, written by the API container onto a shared volume.
 *
 * The seed owns this file because it owns the data; the alternative -- letting
 * the tests describe what they expect to exist -- is two descriptions that have
 * to agree, which is a bug waiting to be written.
 */
export function fixtures(): VisualFixtures {
  if (cached) return cached;
  const path = process.env.VR_FIXTURES ?? "/vr/fixtures.json";
  try {
    cached = JSON.parse(readFileSync(path, "utf8")) as VisualFixtures;
  } catch (error) {
    throw new Error(
      `Could not read the seed manifest at ${path}. The API container writes it after seeding; ` +
        `if it is missing, the stack came up without seeding. (${String(error)})`, { cause: error }
    );
  }
  return cached;
}
