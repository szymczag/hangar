/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it, vi } from "vitest";
import { MAX_REFERENCE_IDS_PER_REQUEST, createWorkItemReferenceBatcher } from "./work-item-reference-batcher";

const setup = () => {
  const scheduled: (() => void)[] = [];
  const fetchReferences = vi.fn(async (_workspaceSlug: string, _projectId: string, _ids: string[]) => []);
  const request = createWorkItemReferenceBatcher(fetchReferences, (callback) => scheduled.push(callback));
  const flush = () => scheduled.splice(0).forEach((callback) => callback());
  return { request, fetchReferences, flush, scheduled };
};

describe("createWorkItemReferenceBatcher", () => {
  it("fetches references of one project in a single request", () => {
    const { request, fetchReferences, flush, scheduled } = setup();

    request("acme", "project-1", "parent-a");
    request("acme", "project-1", "parent-b");
    request("acme", "project-2", "parent-c");

    expect(scheduled).toHaveLength(1);
    flush();
    expect(fetchReferences).toHaveBeenCalledTimes(2);
    expect(fetchReferences).toHaveBeenCalledWith("acme", "project-1", ["parent-a", "parent-b"]);
    expect(fetchReferences).toHaveBeenCalledWith("acme", "project-2", ["parent-c"]);
  });

  it("requests a reference once, even when it stays unresolved", () => {
    const { request, fetchReferences, flush } = setup();

    request("acme", "project-1", "hidden-parent");
    flush();
    request("acme", "project-1", "hidden-parent");
    flush();

    expect(fetchReferences).toHaveBeenCalledTimes(1);
  });

  it("splits large batches", () => {
    const { request, fetchReferences, flush } = setup();

    for (let index = 0; index <= MAX_REFERENCE_IDS_PER_REQUEST; index++) request("acme", "project-1", `id-${index}`);
    flush();

    expect(fetchReferences).toHaveBeenCalledTimes(2);
    expect(fetchReferences.mock.calls[0][2]).toHaveLength(MAX_REFERENCE_IDS_PER_REQUEST);
    expect(fetchReferences.mock.calls[1][2]).toEqual([`id-${MAX_REFERENCE_IDS_PER_REQUEST}`]);
  });

  it("ignores a failed request", async () => {
    const fetchReferences = vi.fn(async () => {
      throw new Error("forbidden");
    });
    const scheduled: (() => void)[] = [];
    const request = createWorkItemReferenceBatcher(fetchReferences, (callback) => scheduled.push(callback));

    request("acme", "project-1", "parent-a");
    expect(() => scheduled[0]()).not.toThrow();
    await Promise.resolve();
  });
});
