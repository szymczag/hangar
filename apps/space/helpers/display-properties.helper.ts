/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { IIssueDisplayProperties } from "@plane/types";

/**
 * The properties a published board shows on each work item. Anyone with the link can read the
 * board, without an account, so it keeps the set Hangar has always shown: the key, state,
 * priority, labels and due date. Upstream makeplane/plane v1.5.0 shows every property
 * (`getComputedDisplayProperties()`), which would put assignees, and with them member names
 * and avatars, on every public card. FORK.md, "Upstream changes not adopted".
 */
export const PUBLIC_BOARD_DISPLAY_PROPERTIES: Readonly<IIssueDisplayProperties> = Object.freeze({
  key: true,
  state: true,
  labels: true,
  priority: true,
  due_date: true,
});
