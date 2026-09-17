/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";
import { ALL_ISSUES, isHierarchyGrouping } from "@plane/constants";
import type { TIssue } from "@plane/types";
import { EIssueLayoutTypes } from "@plane/types";
import { getHierarchyGroupQuickAddData, getResponseGroupIds, orderWorkItemGroups } from "./work-item-hierarchy-groups";

describe("getResponseGroupIds", () => {
  it("returns group ids of a grouped response", () => {
    expect(getResponseGroupIds({ "epic-1": ["a"], None: ["b"] })).toEqual(["epic-1", "None"]);
  });

  it("returns the union of sub-group ids across groups", () => {
    const grouped = { "state-1": { "epic-1": ["a"], None: [] }, "state-2": { "epic-2": ["b"], None: ["c"] } };

    expect(new Set(getResponseGroupIds(grouped, "sub_group"))).toEqual(new Set(["None", "epic-1", "epic-2"]));
  });

  it("has no sub-groups in a flat response", () => {
    expect(getResponseGroupIds({ "epic-1": ["a"] }, "sub_group")).toEqual([]);
    expect(getResponseGroupIds(undefined)).toEqual([]);
  });
});

describe("orderWorkItemGroups", () => {
  const workItems: Record<string, Partial<TIssue>> = {
    late: { id: "late", sequence_id: 30 },
    early: { id: "early", sequence_id: 4 },
  };

  it("orders by identifier, keeps unresolved groups last, and drops the none groups", () => {
    const ordered = orderWorkItemGroups(["late", "unknown", "None", ALL_ISSUES, "early"], (id) =>
      workItems[id] ? (workItems[id] as TIssue) : undefined
    );

    expect(ordered.map(({ workItemId }) => workItemId)).toEqual(["early", "late", "unknown"]);
  });
});

describe("isHierarchyGrouping", () => {
  it("is set by either grouping level", () => {
    expect(isHierarchyGrouping({ layout: EIssueLayoutTypes.LIST, group_by: "epic" })).toBe(true);
    expect(isHierarchyGrouping({ layout: EIssueLayoutTypes.KANBAN, group_by: "state", sub_group_by: "parent" })).toBe(
      true
    );
    expect(isHierarchyGrouping({ layout: EIssueLayoutTypes.KANBAN, group_by: "state", sub_group_by: null })).toBe(
      false
    );
    expect(isHierarchyGrouping(undefined)).toBe(false);
  });

  it("ignores groupings the current layout does not apply", () => {
    expect(isHierarchyGrouping({ layout: EIssueLayoutTypes.LIST, group_by: "state", sub_group_by: "epic" })).toBe(
      false
    );
    expect(isHierarchyGrouping({ layout: EIssueLayoutTypes.SPREADSHEET, group_by: "epic" })).toBe(false);
  });
});

describe("getHierarchyGroupQuickAddData", () => {
  it("creates the work item under the group's parent or Epic", () => {
    expect(getHierarchyGroupQuickAddData("parent", "task-1")).toEqual({ parent_id: "task-1" });
    expect(getHierarchyGroupQuickAddData("epic", "epic-1")).toEqual({ parent_id: "epic-1", epic_id: "epic-1" });
  });

  it("creates a top-level work item in the None group", () => {
    expect(getHierarchyGroupQuickAddData("epic", "None")).toEqual({ parent_id: null, epic_id: null });
    expect(getHierarchyGroupQuickAddData("parent", "None")).toEqual({ parent_id: null });
  });

  it("leaves other groupings alone", () => {
    expect(getHierarchyGroupQuickAddData("state", "state-1")).toBeUndefined();
    expect(getHierarchyGroupQuickAddData(null, "None")).toBeUndefined();
  });
});
