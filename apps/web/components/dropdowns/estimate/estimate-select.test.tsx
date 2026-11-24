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
 * and the spreadsheet through its estimate column. These pin the clear to `null`
 * in that select and on both paths to the update.
 */

// What `EstimateSelect` hands the blocks select, captured on render.
const captured = vi.hoisted(() => ({ onChange: undefined as ((id: string | undefined) => void) | undefined }));
vi.mock("@plane/blocks/property-select", () => ({
  EstimateSelect: (props: { onChange: (id: string | undefined) => void }) => {
    captured.onChange = props.onChange;
    return null;
  },
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

import { SpreadsheetEstimateColumn } from "@/components/issues/issue-layouts/spreadsheet/columns/estimate-column";
import { EstimateSelect } from "./estimate-select";

describe("EstimateSelect", () => {
  it("emits null when the estimate is cleared", () => {
    const onChange = vi.fn();
    renderToStaticMarkup(
      <EstimateSelect value="point-1" onChange={onChange} projectId="project-1" variant="table-cell" />
    );

    captured.onChange?.(undefined);

    expect(onChange).toHaveBeenCalledWith(null);
  });

  it("passes a picked estimate point through", () => {
    const onChange = vi.fn();
    renderToStaticMarkup(
      <EstimateSelect value={undefined} onChange={onChange} projectId="project-1" variant="table-cell" />
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
