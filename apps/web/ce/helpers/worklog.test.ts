/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { EUserPermissions } from "@plane/types";

import { canLogWorkForRole, canViewWorklogsForRole, isWorklogHiddenForRole } from "./worklog";

// Worklogs are confidential from guests (FORK.md, "Security invariants", S20).
// The API refuses them; this keeps the UI from asking and from rendering them.
const ROLE = EUserPermissions;
const here = path.dirname(fileURLToPath(import.meta.url));

describe("canViewWorklogsForRole", () => {
  it("lets project admins and members see worklogs", () => {
    expect(canViewWorklogsForRole(ROLE.ADMIN)).toBe(true);
    expect(canViewWorklogsForRole(ROLE.MEMBER)).toBe(true);
  });

  it("hides worklogs from guests and from an unknown role", () => {
    expect(canViewWorklogsForRole(ROLE.GUEST)).toBe(false);
    expect(canViewWorklogsForRole(undefined)).toBe(false);
    expect(canViewWorklogsForRole(0)).toBe(false);
    expect(canViewWorklogsForRole(-1)).toBe(false);
  });

  it.each([
    "../components/issues/issue-details/sidebar-properties.tsx",
    "../../components/issues/issue-detail/issue-activity/root.tsx",
  ])("%s gates worklogs on the helper", (file) => {
    const source = readFileSync(path.join(here, file), "utf8");
    expect(source).toMatch(/canViewWorklogs\s*=\s*canViewWorklogsForRole\(/);
  });
});

describe("isWorklogHiddenForRole", () => {
  it("hides worklog rows from guests and from an unknown role", () => {
    expect(isWorklogHiddenForRole("worklog", ROLE.GUEST)).toBe(true);
    expect(isWorklogHiddenForRole("worklog", undefined)).toBe(true);
  });

  it("shows worklog rows to project admins and members", () => {
    expect(isWorklogHiddenForRole("worklog", ROLE.ADMIN)).toBe(false);
    expect(isWorklogHiddenForRole("worklog", ROLE.MEMBER)).toBe(false);
  });

  it("never hides any other kind of row", () => {
    for (const field of ["state", "comment", "priority", undefined, null]) {
      expect(isWorklogHiddenForRole(field, ROLE.GUEST)).toBe(false);
    }
  });

  // The profile's activity feeds and the inbox list rows of every kind, and a
  // worklog row prints the logged duration.
  it.each([
    ["../../components/profile/activity/activity-list.tsx", /isWorklogHiddenForRole\(\s*activityItem\.field,/],
    ["../../components/profile/overview/activity.tsx", /isWorklogHiddenForRole\(\s*activity\.field,/],
    [
      "../../components/workspace-notifications/sidebar/notification-card/item.tsx",
      /isWorklogHiddenForRole\(\s*notificationField,/,
    ],
  ])("%s leaves worklog rows out behind the helper", (file, pattern) => {
    expect(readFileSync(path.join(here, file), "utf8")).toMatch(pattern);
  });
});

describe("canLogWorkForRole", () => {
  it("offers logging time to project admins, assigned or not", () => {
    expect(canLogWorkForRole({ role: ROLE.ADMIN, isAssignee: false, isIntakeIssue: false })).toBe(true);
    expect(canLogWorkForRole({ role: ROLE.ADMIN, isAssignee: true, isIntakeIssue: false })).toBe(true);
  });

  it("offers it to members only on work items assigned to them", () => {
    expect(canLogWorkForRole({ role: ROLE.MEMBER, isAssignee: true, isIntakeIssue: false })).toBe(true);
    expect(canLogWorkForRole({ role: ROLE.MEMBER, isAssignee: false, isIntakeIssue: false })).toBe(false);
  });

  it("never offers it to guests or an unknown role, even when assigned", () => {
    expect(canLogWorkForRole({ role: ROLE.GUEST, isAssignee: true, isIntakeIssue: false })).toBe(false);
    expect(canLogWorkForRole({ role: undefined, isAssignee: true, isIntakeIssue: false })).toBe(false);
  });

  it("never offers it on an intake work item", () => {
    expect(canLogWorkForRole({ role: ROLE.ADMIN, isAssignee: true, isIntakeIssue: true })).toBe(false);
  });
});

// Upstream v1.5.0 renders the detail sidebar and the peek from one component
// without a slot for Hangar's rows; the slot that carries the worklog must stay
// mounted on both surfaces.
describe("the worklog slot in the work item properties", () => {
  const read = (file: string) => readFileSync(path.join(here, file), "utf8");

  it("is mounted by the shared sidebar sections", () => {
    expect(read("../../components/issues/issue-detail/sidebar-sections.tsx")).toMatch(
      /<WorkItemSidebarHangarProperties\b/
    );
  });

  it.each(["../../components/issues/issue-detail/sidebar.tsx", "../../components/issues/peek-overview/properties.tsx"])(
    "%s renders the shared sidebar sections",
    (file) => {
      expect(read(file)).toMatch(/<IssueDetailSidebarSections\b/);
    }
  );

  it("passes the worklog property the guest gate", () => {
    expect(read("../components/issues/issue-details/sidebar-properties.tsx")).toMatch(
      /<IssueWorklogProperty[\s\S]*?canViewWorklogs=\{canViewWorklogs\}/
    );
  });

  it("renders worklog entries in the activity feed only behind the gate", () => {
    expect(read("../../components/issues/issue-detail/issue-activity/activity-comment-root.tsx")).toMatch(
      /canViewWorklogs && activityComment\.activity_type === "WORKLOG"/
    );
  });
});
