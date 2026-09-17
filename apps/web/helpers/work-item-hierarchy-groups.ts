/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { ALL_ISSUES } from "@plane/constants";
import type { TGroupedIssues, TIssue, TSubGroupedIssues } from "@plane/types";

/**
 * The group ids present in a grouped response. Parent and Epic groups are not a
 * fixed list like states or priorities, so their columns come from the response.
 */
export const getResponseGroupIds = (
  groupedIssueIds: TGroupedIssues | TSubGroupedIssues | undefined,
  level: "group" | "sub_group" = "group"
): string[] => {
  if (!groupedIssueIds || Array.isArray(groupedIssueIds)) return [];
  if (level === "group") return Object.keys(groupedIssueIds);
  const subGroupIds = new Set<string>();
  Object.values(groupedIssueIds).forEach((group) => {
    if (group && !Array.isArray(group)) Object.keys(group).forEach((subGroupId) => subGroupIds.add(subGroupId));
  });
  return Array.from(subGroupIds);
};

/** Work item groups in identifier order; unresolved ones last. The "None" group is left to the caller. */
export const orderWorkItemGroups = (
  groupIds: string[] | undefined,
  getWorkItem: (workItemId: string) => TIssue | undefined
): { workItemId: string; workItem: TIssue | undefined }[] => {
  const groups: { workItemId: string; workItem: TIssue | undefined }[] = [];
  for (const groupId of groupIds ?? []) {
    if (groupId === "None" || groupId === ALL_ISSUES) continue;
    groups.push({ workItemId: groupId, workItem: getWorkItem(groupId) });
  }
  return groups.toSorted(
    (first, second) =>
      (first.workItem?.sequence_id ?? Number.MAX_SAFE_INTEGER) -
      (second.workItem?.sequence_id ?? Number.MAX_SAFE_INTEGER)
  );
};
