/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { readFileSync } from "node:fs";
import path from "node:path";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { TIssue } from "@plane/types";

/**
 * "No estimate" must reach the API as `null`. JSON drops `undefined` keys, so a
 * PATCH built from `undefined` arrives without `estimate_point` and the old
 * estimate stays (fixed in phase 4a for the 1.4 shim, see `../estimate.test.tsx`).
 *
 * Since phase 4b every work item layout edits the estimate through upstream's
 * `EstimateSelect`: the list, board and calendar rows through `all-properties.tsx`
 * and the spreadsheet through its estimate column. Since phase 4c the create and
 * edit dialog does too. These pin the clear to `null` in that select and on every
 * path to the update.
 */

// What `EstimateSelect` hands the blocks select, captured on render.
const captured = vi.hoisted(() => ({ onChange: undefined as ((id: string | undefined) => void) | undefined }));
vi.mock("@plane/blocks/property-select", () => ({
  EstimateSelect: (props: { onChange: (id: string | undefined) => void }) => {
    captured.onChange = props.onChange;
    return null;
  },
  // The dialog's date pills; only the estimate matters here.
  DateSelect: () => null,
}));
vi.mock("next/navigation", () => ({ useParams: () => ({ workspaceSlug: "acme" }) }));
vi.mock("@plane/i18n", () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
vi.mock("@/hooks/store/estimates", () => ({
  useProjectEstimates: () => ({
    currentActiveEstimateIdByProjectId: () => undefined,
    areEstimateEnabledByProjectId: () => true,
    getProjectEstimates: async () => undefined,
    getEstimateById: () => undefined,
  }),
}));
vi.mock("@/hooks/store/estimates/use-estimate", () => ({ useEstimate: () => undefined }));
// The create dialog's other properties, which read stores of their own.
vi.mock("@/components/dropdowns/cycle/cycle-select", () => ({ CycleSelect: () => null }));
vi.mock("@/components/dropdowns/label/label-select", () => ({ LabelSelect: () => null }));
vi.mock("@/components/dropdowns/member/member-select", () => ({ MemberSelect: () => null }));
vi.mock("@/components/dropdowns/module/module-select", () => ({ ModuleSelect: () => null }));
vi.mock("@/components/dropdowns/priority/priority-select", () => ({ PrioritySelect: () => null }));
vi.mock("@/components/dropdowns/state/state-select", () => ({ StateSelect: () => null }));
vi.mock("@/components/issues/parent-issues-list-modal", () => ({ ParentIssuesListModal: () => null }));
vi.mock("@/components/issues/issue-detail/issue-identifier", () => ({ IssueIdentifier: () => null }));
vi.mock("@/plane-web/components/issues/issue-modal/issue-type-select", () => ({ IssueTypeSelect: () => null }));
vi.mock("@/hooks/store/use-project", () => ({ useProject: () => ({ getProjectById: () => undefined }) }));
vi.mock("@/hooks/store/use-project-state", () => ({
  useProjectState: () => ({ getProjectDefaultStateId: () => undefined }),
}));
vi.mock("@/hooks/store/user", () => ({ useUserProfile: () => ({ data: undefined }) }));
vi.mock("@/hooks/use-platform-os", () => ({ usePlatformOS: () => ({ isMobile: false }) }));

import { useForm } from "react-hook-form";
import type { UseFormReturn } from "react-hook-form";
import { getChangedIssuefields } from "@plane/utils";
import { IssueDefaultProperties } from "@/components/issues/issue-modal/components/default-properties";
import { SpreadsheetEstimateColumn } from "@/components/issues/issue-layouts/spreadsheet/columns/estimate-column";
import { EstimateSelect } from "./estimate-select";

describe("EstimateSelect", () => {
  it("emits null when the estimate is cleared", () => {
    const onChange = vi.fn();
    renderToStaticMarkup(
      <EstimateSelect value="point-1" onChange={onChange} projectId="project-1" variant="pill-md" />
    );

    captured.onChange?.(undefined);

    expect(onChange).toHaveBeenCalledWith(null);
  });

  it("passes a picked estimate point through", () => {
    const onChange = vi.fn();
    renderToStaticMarkup(
      <EstimateSelect value={undefined} onChange={onChange} projectId="project-1" variant="pill-md" />
    );

    captured.onChange?.("point-2");

    expect(onChange).toHaveBeenCalledWith("point-2");
  });
});

describe("the spreadsheet estimate column", () => {
  it("sends estimate_point: null for No estimate", () => {
    const onChange = vi.fn();
    const issue = { id: "issue-1", project_id: "project-1", estimate_point: "point-1" } as TIssue;
    renderToStaticMarkup(
      <SpreadsheetEstimateColumn issue={issue} onChange={onChange} disabled={false} onClose={() => undefined} />
    );

    captured.onChange?.(undefined);

    expect(onChange).toHaveBeenCalledTimes(1);
    const [, data] = onChange.mock.calls[0] as [TIssue, Partial<TIssue>];
    expect(data).toEqual({ estimate_point: null });
    // The key is present, so the PATCH body carries it.
    expect(JSON.stringify(data)).toBe('{"estimate_point":null}');
  });
});

describe("the list, board and calendar row properties", () => {
  // `all-properties.tsx` reads a dozen stores, so the wiring is pinned in its
  // source: the row hands upstream's select a handler that forwards `null`.
  const source = readFileSync(
    path.resolve(__dirname, "../../issues/issue-layouts/properties/all-properties.tsx"),
    "utf8"
  );

  it("edits the estimate through EstimateSelect", () => {
    expect(source).toContain(
      'import { EstimateSelect, getEstimatePointDisplayValue } from "@/components/dropdowns/estimate/estimate-select";'
    );
    expect(source).toMatch(/<EstimateSelect[\s\S]*?onChange=\{handleEstimate\}/);
  });

  it("forwards null to the update unchanged", () => {
    expect(source).toMatch(
      /const handleEstimate = async \(value: string \| null\) => \{\s*if \(updateIssue\) await updateIssue\(issue\.project_id, issue\.id, \{ estimate_point: value \}\);/
    );
  });
});

describe("the work item create and edit dialog", () => {
  /** Renders the dialog's property row on a form holding `estimate_point: "point-1"`. */
  function renderDialogProperties(): UseFormReturn<TIssue> {
    const form: { current?: UseFormReturn<TIssue> } = {};
    function Dialog() {
      const methods = useForm<TIssue>({ defaultValues: { estimate_point: "point-1" } });
      form.current = methods;
      return (
        <IssueDefaultProperties
          control={methods.control}
          id="issue-1"
          projectId="project-1"
          workspaceSlug="acme"
          selectedParentIssue={null}
          startDate={null}
          targetDate={null}
          parentId={null}
          isDraft={false}
          handleFormChange={() => undefined}
          setSelectedParentIssue={() => undefined}
        />
      );
    }
    renderToStaticMarkup(<Dialog />);
    if (!form.current) throw new Error("the dialog did not render its form");
    return form.current;
  }

  it("stores null in the form for No estimate", () => {
    const form = renderDialogProperties();

    captured.onChange?.(undefined);

    expect(form.getValues("estimate_point")).toBeNull();
  });

  it("sends estimate_point: null when the edit is saved", () => {
    const form = renderDialogProperties();

    captured.onChange?.(undefined);

    // The edit dialog sends only the dirty fields, built the way `form.tsx` builds them.
    const payload = getChangedIssuefields(form.getValues(), { estimate_point: true });
    expect(JSON.stringify(payload)).toBe('{"estimate_point":null}');
  });
});
