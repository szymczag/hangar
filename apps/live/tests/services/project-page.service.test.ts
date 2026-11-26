/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it, vi } from "vitest";

const PAGE_ID = "11111111-1111-4111-8111-111111111111";
const PROJECT_ID = "22222222-2222-4222-8222-222222222222";

vi.mock("@plane/logger", () => ({ logger: { info: vi.fn(), error: vi.fn(), warn: vi.fn(), debug: vi.fn() } }));

// the real APIService pulls in unbuilt workspace packages; only `get` and the header matter here
vi.mock("@/services/api.service", () => ({
  APIService: class {
    private headers: Record<string, string> = {};
    get = vi.fn();
    setHeader(key: string, value: string) {
      this.headers[key] = value;
    }
    getHeader() {
      return this.headers;
    }
  },
}));

import { ProjectPageService } from "@/services/page/project-page.service";

const service = (data: unknown) => {
  const s = new ProjectPageService({ workspaceSlug: "ws", projectId: PROJECT_ID, cookie: "session=c" });
  const get = vi.spyOn(s, "get").mockResolvedValue({ data } as never);
  return { s, get };
};

describe("ProjectPageService.fetchUserMentions", () => {
  it("reads the workspace member list with the exporting user's own session", async () => {
    const { s, get } = service([]);
    await s.fetchUserMentions(PAGE_ID);
    expect(get).toHaveBeenCalledTimes(1);
    expect(get).toHaveBeenCalledWith("/api/workspaces/ws/members/", { headers: { Cookie: "session=c" } });
  });

  it("keeps only id, display name and avatar of each member, for guest and member responses alike", async () => {
    const { s } = service([
      // guest shape: id, member, role
      { id: "wm-1", role: 5, member: { id: "u-1", display_name: "ada", first_name: "Ada", avatar_url: "/a.png" } },
      // member/admin shape carries more fields, none of which are kept
      {
        id: "wm-2",
        role: 15,
        is_active: true,
        member: { id: "u-2", display_name: "bob", email: "bob@example.com", avatar_url: null },
      },
    ]);

    await expect(s.fetchUserMentions(PAGE_ID)).resolves.toEqual([
      { id: "u-1", display_name: "ada", avatar_url: "/a.png" },
      { id: "u-2", display_name: "bob", avatar_url: undefined },
    ]);
  });

  it.each([
    ["a non-array body", { error: "x" }],
    ["rows without a usable member", [null, {}, { member: null }, { member: { id: 1, display_name: "x" } }]],
  ])("returns no mentions for %s", async (_label, data) => {
    const { s } = service(data);
    await expect(s.fetchUserMentions(PAGE_ID)).resolves.toEqual([]);
  });

  it("propagates an API refusal so the export falls back to unresolved mentions", async () => {
    const { s, get } = service([]);
    get.mockRejectedValueOnce(Object.assign(new Error("forbidden"), { response: { status: 403 } }));
    await expect(s.fetchUserMentions(PAGE_ID)).rejects.toBeDefined();
  });
});
