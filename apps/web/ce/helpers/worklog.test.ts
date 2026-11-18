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

import { canViewWorklogsForRole } from "./worklog";

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

  it.each(["../../components/issues/issue-detail/sidebar.tsx", "../../components/issues/peek-overview/properties.tsx"])(
    "%s gates worklogs on the helper",
    (file) => {
      const source = readFileSync(path.join(here, file), "utf8");
      expect(source).toMatch(/canViewWorklogs\s*=\s*canViewWorklogsForRole\(/);
    }
  );
});
