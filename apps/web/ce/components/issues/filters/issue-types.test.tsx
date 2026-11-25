/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SUB_WORK_ITEM_AVAILABLE_FILTERS_FOR_WORK_ITEM_PAGE } from "@plane/constants";
import type { TIssue } from "@plane/types";

const state = vi.hoisted(() => ({
  types: [] as { id: string; name: string; is_active: boolean }[],
  submenu: null as null | { label: string; options: { value: string; label: string }[] },
  projectId: undefined as string | undefined | null,
}));

vi.mock("next/navigation", () => ({ useParams: () => ({ workspaceSlug: "vr" }) }));
vi.mock("@plane/i18n", () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
vi.mock("@/plane-web/hooks/use-issue-types", () => ({
  useIssueTypes: (_workspaceSlug: string, projectId: string | undefined | null) => {
    state.projectId = projectId;
    return { issueTypes: state.types };
  },
}));
vi.mock("@/components/common/filters/filter-submenu", () => ({
  FilterSubmenu: (props: { label: string; options: { value: string; label: string }[] }) => {
    state.submenu = props;
    return <span>{props.label}</span>;
  },
}));

import { getFilteredWorkItems } from "@/store/issue/helpers/base-issues-utils";
import { FilterIssueTypes } from "./issue-types";

const here = path.dirname(fileURLToPath(import.meta.url));

describe("FilterIssueTypes", () => {
  beforeEach(() => {
    state.submenu = null;
    state.projectId = undefined;
  });

  it("offers the project's active types as one filter row", () => {
    state.types = [
      { id: "task", name: "Task", is_active: true },
      { id: "retired", name: "Retired", is_active: false },
      { id: "workshop", name: "Workshop", is_active: true },
    ];
    renderToStaticMarkup(<FilterIssueTypes appliedFilters={["task"]} handleUpdate={() => {}} projectId="project" />);
    expect(state.projectId).toBe("project");
    expect(state.submenu?.label).toBe("issue.display.properties.issue_type");
    expect(state.submenu?.options.map((option) => [option.value, option.label])).toEqual([
      ["task", "Task"],
      ["workshop", "Workshop"],
    ]);
  });

  it("renders nothing while the project has no active type", () => {
    state.types = [{ id: "retired", name: "Retired", is_active: false }];
    expect(
      renderToStaticMarkup(<FilterIssueTypes appliedFilters={null} handleUpdate={() => {}} projectId="project" />)
    ).toBe("");
    expect(state.submenu).toBeNull();
  });
});

describe("the sub-work item type filter", () => {
  it("is offered by the sub-work items filters menu", () => {
    expect(SUB_WORK_ITEM_AVAILABLE_FILTERS_FOR_WORK_ITEM_PAGE).toContain("issue_type");
    const menu = readFileSync(
      path.join(here, "../../../../components/issues/issue-detail-widgets/sub-issues/filters.tsx"),
      "utf8"
    );
    expect(menu).toMatch(/isFilterEnabled\("issue_type"\) && \(\s*<FilterIssueTypes/);
  });

  it("keeps the sub-work items of the chosen types", () => {
    const items = [
      { id: "a", type_id: "task" },
      { id: "b", type_id: "workshop" },
      { id: "c", type_id: null },
    ] as unknown as TIssue[];
    expect(getFilteredWorkItems(items, { issue_type: ["workshop"] }).map((item) => item.id)).toEqual(["b"]);
    expect(getFilteredWorkItems(items, { issue_type: [] }).map((item) => item.id)).toEqual(["a", "b", "c"]);
  });
});
