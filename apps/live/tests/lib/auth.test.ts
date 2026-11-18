/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

const { currentUser, getPageAccess } = vi.hoisted(() => ({ currentUser: vi.fn(), getPageAccess: vi.fn() }));
vi.mock("@/services/user.service", () => ({
  UserService: class {
    currentUser = currentUser;
    getPageAccess = getPageAccess;
  },
}));

import { onAuthenticate } from "@/lib/auth";
import { AppError } from "@/lib/errors";
import type { HocusPocusServerContext } from "@/types";

const PAGE_ID = "11111111-1111-4111-8111-111111111111";

const connect = (
  documentName = PAGE_ID,
  documentType: string | null = "project_page",
  user: { id: string; cookie: string } = { id: "user-1", cookie: "session=abc" }
) => {
  const context = {} as HocusPocusServerContext;
  const connectionConfig = { readOnly: false };
  const result = onAuthenticate({
    requestHeaders: {},
    // a hostile client picks any projectId it likes
    requestParameters: new URLSearchParams({
      workspaceSlug: "ws",
      projectId: "attacker-project",
      ...(documentType === null ? {} : { documentType }),
    }),
    context,
    token: JSON.stringify(user),
    documentName,
    connectionConfig,
  });
  return { result, context, connection: connectionConfig };
};

describe("onAuthenticate page authorization", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    currentUser.mockResolvedValue({ id: "user-1", display_name: "U" });
  });

  it("rejects a connection to a page the user cannot access", async () => {
    // APIService rejects with an AppError carrying the response status.
    getPageAccess.mockRejectedValue(new AppError("Page not found", { statusCode: 404 }));
    await expect(connect().result).rejects.toMatchObject({ code: "AUTH_PAGE_ACCESS_DENIED" });
    expect(getPageAccess).toHaveBeenCalledWith("session=abc", "ws", PAGE_ID, "view");
  });

  it("refuses a failed check under its own code, not as a denial", async () => {
    getPageAccess.mockRejectedValue(new AppError("Too many requests", { statusCode: 429, code: "ERR_BAD_RESPONSE" }));
    await expect(connect().result).rejects.toMatchObject({ code: "ERR_BAD_RESPONSE" });
  });

  it("refuses the connection when the answer has no read_only", async () => {
    getPageAccess.mockResolvedValue({ project_id: "real-project" });
    await expect(connect().result).rejects.toMatchObject({ code: "AUTH_PAGE_ACCESS_UNKNOWN" });
  });

  it.each(["server_agent", "ai_agent", "sync_agent", "workspace_page", "bogus", null])(
    "rejects documentType %s before any check",
    async (type) => {
      await expect(connect(PAGE_ID, type).result).rejects.toMatchObject({ code: "AUTH_INVALID_DOCUMENT_TYPE" });
      expect(currentUser).not.toHaveBeenCalled();
      expect(getPageAccess).not.toHaveBeenCalled();
    }
  );

  it("uses the checked page's project and read-only flag, not the socket's", async () => {
    getPageAccess.mockResolvedValue({ project_id: "real-project", read_only: true });
    const { result, context, connection } = connect();
    await expect(result).resolves.toEqual({ user: { id: "user-1", name: "U" } });
    expect(context.projectId).toBe("real-project");
    expect(connection.readOnly).toBe(true);
  });

  it("checks every connection to an already-open page, so a second user without access is refused", async () => {
    // Hocuspocus runs onAuthenticate once per socket and document, but loads the document only for the first
    // socket; the check must not depend on the document already being open.
    currentUser.mockImplementation(async (cookie: string) =>
      cookie === "session=owner" ? { id: "owner", display_name: "Owner" } : { id: "outsider", display_name: "Out" }
    );
    getPageAccess.mockImplementation(async (cookie: string) => {
      if (cookie === "session=owner") return { project_id: "real-project", read_only: false };
      throw new AppError("Page not found", { statusCode: 404 });
    });

    const first = connect(PAGE_ID, "project_page", { id: "owner", cookie: "session=owner" });
    await expect(first.result).resolves.toEqual({ user: { id: "owner", name: "Owner" } });
    expect(first.connection.readOnly).toBe(false);

    const second = connect(PAGE_ID, "project_page", { id: "outsider", cookie: "session=outsider" });
    await expect(second.result).rejects.toMatchObject({ code: "AUTH_PAGE_ACCESS_DENIED" });
    expect(getPageAccess).toHaveBeenNthCalledWith(2, "session=outsider", "ws", PAGE_ID, "view");
    expect(second.context.projectId).toBeUndefined();
  });

  it("opens a guest's connection read-only while an editor on the same page stays writable", async () => {
    currentUser.mockImplementation(async (cookie: string) => ({ id: cookie.slice(8), display_name: "U" }));
    getPageAccess.mockImplementation(async (cookie: string) => ({
      project_id: "real-project",
      read_only: cookie === "session=guest",
    }));

    const editor = connect(PAGE_ID, "project_page", { id: "editor", cookie: "session=editor" });
    const guest = connect(PAGE_ID, "project_page", { id: "guest", cookie: "session=guest" });
    await Promise.all([editor.result, guest.result]);

    expect(editor.connection.readOnly).toBe(false);
    expect(guest.connection.readOnly).toBe(true);
  });
});
