/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";
import type { IWorkspace } from "@plane/types";
import { workspacesAllowingApiTokens } from "./api-token-eligibility";

const workspace = (slug: string, role?: number) => ({ slug, role }) as IWorkspace;

describe("workspacesAllowingApiTokens", () => {
  it("offers only the workspaces whose role meets the threshold", () => {
    const result = workspacesAllowingApiTokens(
      [workspace("guest-only", 5), workspace("member", 15), workspace("admin", 20)],
      15
    );

    expect(result.map((w) => w.slug)).toEqual(["member", "admin"]);
  });

  it("offers none when no membership qualifies, which is what withdraws the button", () => {
    expect(workspacesAllowingApiTokens([workspace("guest-only", 5)], 15)).toEqual([]);
  });

  it("falls back to the server's own default when the instance reports nothing", () => {
    // Guessing higher would hide a feature that works; the server refuses either way.
    const result = workspacesAllowingApiTokens([workspace("guest-only", 5), workspace("member", 15)], undefined);

    expect(result.map((w) => w.slug)).toEqual(["guest-only", "member"]);
  });

  it("keeps a workspace whose role the list did not report", () => {
    // Membership is established; only the role is unknown, and the server answers
    // properly. Dropping it would hide a workspace someone may well be admin of.
    expect(workspacesAllowingApiTokens([workspace("unknown")], 20).map((w) => w.slug)).toEqual(["unknown"]);
  });

  it("accepts the store's keyed shape as well as a list", () => {
    const keyed = { a: workspace("member", 15), b: workspace("guest", 5) };

    expect(workspacesAllowingApiTokens(keyed, 15).map((w) => w.slug)).toEqual(["member"]);
  });

  it("returns nothing rather than throwing when there are no workspaces yet", () => {
    expect(workspacesAllowingApiTokens(undefined, 15)).toEqual([]);
  });
});
