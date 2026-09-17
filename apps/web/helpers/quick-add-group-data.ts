/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TIssue } from "@plane/types";

const NONE = "None";

/**
 * The values a work item created from a group's quick add inherits from that group.
 *
 * Extracted from the list and board group components, which both carried the same
 * branch chain inline. `ignoreNoneFor` keeps each layout's own handling of the
 * "None" group: the list leaves cycle and module unset there, the board does not.
 */
const groupQuickAddData = (
  groupByKey: string | null | undefined,
  value: string,
  ignoreNoneFor: string[]
): Partial<TIssue> => {
  if (!groupByKey) return {};
  if (ignoreNoneFor.includes(groupByKey) && value === NONE) return {};

  switch (groupByKey) {
    case "state":
      return { state_id: value };
    case "priority":
      return { priority: value as TIssue["priority"] };
    case "labels":
      return { label_ids: [value] };
    case "assignees":
      return { assignee_ids: [value] };
    case "cycle":
      return { cycle_id: value };
    case "module":
      return { module_ids: [value] };
    case "created_by":
      return {};
    case "parent":
      return { parent_id: value === NONE ? null : value };
    case "epic": {
      const epicId = value === NONE ? null : value;
      return { parent_id: epicId, epic_id: epicId };
    }
    default:
      return { [groupByKey]: value } as Partial<TIssue>;
  }
};

export const getListGroupQuickAddData = (groupByKey: string | null | undefined, value: string): Partial<TIssue> =>
  groupQuickAddData(groupByKey, value, ["labels", "assignees", "cycle", "module"]);

export const getBoardGroupQuickAddData = (groupByKey: string | null | undefined, value: string): Partial<TIssue> =>
  groupQuickAddData(groupByKey, value, ["labels", "assignees"]);
