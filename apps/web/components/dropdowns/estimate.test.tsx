/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

// The props the shim hands upstream's EstimateSelect, captured on render.
const captured = vi.hoisted(() => ({ onChange: undefined as ((value: string | null) => void) | undefined }));
vi.mock("./estimate/estimate-select", () => ({
  EstimateSelect: (props: { onChange: (value: string | null) => void }) => {
    captured.onChange = props.onChange;
    return null;
  },
}));
vi.mock("./compat-frame", () => ({
  DropdownCompatFrame: ({ children }: React.PropsWithChildren) => <>{children}</>,
}));
vi.mock("./compat", () => ({
  toSelectTooltip: () => undefined,
  toSelectVariant: () => "select-ghost-md",
  toTriggerClassName: () => undefined,
}));

import { EstimateDropdown } from "./estimate";

/** Renders the shim and returns what its caller receives when `value` is picked. */
function pick(value: string | null): unknown[] {
  const onChange = vi.fn();
  renderToStaticMarkup(
    <EstimateDropdown value="point-1" onChange={onChange} projectId="project-1" buttonVariant="border-with-text" />
  );
  captured.onChange?.(value);
  return onChange.mock.calls.map(([received]) => received as unknown);
}

describe("EstimateDropdown", () => {
  // JSON drops `undefined` keys, so `{ estimate_point: undefined }` reached the
  // server as `{}` and the old estimate stayed.
  it('passes "No estimate" on as null, which clears the field', () => {
    expect(pick(null)).toEqual([null]);
  });

  it("passes a chosen estimate point on unchanged", () => {
    expect(pick("point-2")).toEqual(["point-2"]);
  });
});
