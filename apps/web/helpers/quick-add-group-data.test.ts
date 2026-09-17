/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";
import { getBoardGroupQuickAddData, getListGroupQuickAddData } from "./quick-add-group-data";

describe("group quick add data", () => {
  it("inherits the group's own value", () => {
    expect(getListGroupQuickAddData("state", "state-1")).toEqual({ state_id: "state-1" });
    expect(getListGroupQuickAddData("priority", "urgent")).toEqual({ priority: "urgent" });
    expect(getListGroupQuickAddData("labels", "label-1")).toEqual({ label_ids: ["label-1"] });
    expect(getListGroupQuickAddData("assignees", "member-1")).toEqual({ assignee_ids: ["member-1"] });
    expect(getListGroupQuickAddData("cycle", "cycle-1")).toEqual({ cycle_id: "cycle-1" });
    expect(getListGroupQuickAddData("module", "module-1")).toEqual({ module_ids: ["module-1"] });
  });

  it("inherits nothing from a grouping that cannot be set", () => {
    expect(getListGroupQuickAddData("created_by", "member-1")).toEqual({});
    expect(getListGroupQuickAddData(null, "None")).toEqual({});
    expect(getListGroupQuickAddData(undefined, "None")).toEqual({});
  });

  it("creates the work item under a parent or Epic group", () => {
    expect(getListGroupQuickAddData("parent", "task-1")).toEqual({ parent_id: "task-1" });
    expect(getListGroupQuickAddData("epic", "epic-1")).toEqual({ parent_id: "epic-1", epic_id: "epic-1" });
    expect(getBoardGroupQuickAddData("epic", "epic-1")).toEqual({ parent_id: "epic-1", epic_id: "epic-1" });
  });

  it("creates a top-level work item in a None hierarchy group", () => {
    expect(getListGroupQuickAddData("parent", "None")).toEqual({ parent_id: null });
    expect(getListGroupQuickAddData("epic", "None")).toEqual({ parent_id: null, epic_id: null });
  });

  it("keeps each layout's handling of the None group", () => {
    // The list leaves these unset, the board passes the group value through.
    expect(getListGroupQuickAddData("cycle", "None")).toEqual({});
    expect(getListGroupQuickAddData("module", "None")).toEqual({});
    expect(getBoardGroupQuickAddData("cycle", "None")).toEqual({ cycle_id: "None" });
    expect(getBoardGroupQuickAddData("module", "None")).toEqual({ module_ids: ["None"] });
    expect(getListGroupQuickAddData("labels", "None")).toEqual({});
    expect(getBoardGroupQuickAddData("labels", "None")).toEqual({});
  });
});
