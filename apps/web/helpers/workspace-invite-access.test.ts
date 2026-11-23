/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";
import { canInviteToWorkspace, canManageWorkspaceInvitation } from "./workspace-invite-access";

const ADMIN = 20;
const MEMBER = 15;
const GUEST = 5;

describe("canInviteToWorkspace", () => {
  it("lets an admin invite whatever the instance says", () => {
    expect(canInviteToWorkspace(ADMIN, false)).toBe(true);
    expect(canInviteToWorkspace(ADMIN, undefined)).toBe(true);
  });

  it("lets a member invite only where the instance allows it", () => {
    expect(canInviteToWorkspace(MEMBER, true)).toBe(true);
    expect(canInviteToWorkspace(MEMBER, false)).toBe(false);
    // An instance that did not report the flag is treated as off, as the server defaults.
    expect(canInviteToWorkspace(MEMBER, undefined)).toBe(false);
  });

  it("never lets a guest or an unknown role invite", () => {
    expect(canInviteToWorkspace(GUEST, true)).toBe(false);
    expect(canInviteToWorkspace(undefined, true)).toBe(false);
  });
});

describe("canManageWorkspaceInvitation", () => {
  it("lets an admin manage any invitation", () => {
    expect(canManageWorkspaceInvitation(ADMIN, false, "someone-else", "me")).toBe(true);
    expect(canManageWorkspaceInvitation(ADMIN, false, null, "me")).toBe(true);
  });

  it("lets a member manage only what they sent, and only while members may invite", () => {
    expect(canManageWorkspaceInvitation(MEMBER, true, "me", "me")).toBe(true);
    expect(canManageWorkspaceInvitation(MEMBER, true, "someone-else", "me")).toBe(false);
    expect(canManageWorkspaceInvitation(MEMBER, false, "me", "me")).toBe(false);
  });

  it("leaves an invitation with no recorded sender to the admins", () => {
    expect(canManageWorkspaceInvitation(MEMBER, true, null, "me")).toBe(false);
    expect(canManageWorkspaceInvitation(MEMBER, true, undefined, undefined)).toBe(false);
  });

  it("never lets a guest manage one, not even their own", () => {
    expect(canManageWorkspaceInvitation(GUEST, true, "me", "me")).toBe(false);
  });
});
