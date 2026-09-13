/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { EUserWorkspaceRoles } from "@plane/types";

const state = vi.hoisted(() => ({ enabled: undefined as boolean | undefined, role: 20 }));
vi.mock("mobx-react", () => ({ observer: (component: unknown) => component }));
vi.mock("next/navigation", () => ({
  useParams: () => ({ workspaceSlug: "test-workspace" }),
  usePathname: () => "/test-workspace/capacity/",
}));
vi.mock("next/link", () => ({
  default: ({ children, href }: React.PropsWithChildren<{ href: string }>) => <a href={href}>{children}</a>,
}));
vi.mock("@plane/constants", () => ({
  WORKSPACE_SIDEBAR_DYNAMIC_NAVIGATION_ITEMS_LINKS: [],
  WORKSPACE_SIDEBAR_STATIC_NAVIGATION_ITEMS: {},
  WORKSPACE_SIDEBAR_STATIC_NAVIGATION_ITEMS_LINKS: [],
  WORKSPACE_SIDEBAR_STATIC_PINNED_NAVIGATION_ITEMS_LINKS: [],
  EUserPermissionsLevel: { WORKSPACE: "WORKSPACE" },
}));
vi.mock("@plane/i18n", () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
vi.mock("@plane/propel/icons", () => ({ ChevronRightIcon: () => null }));
vi.mock("@plane/utils", () => ({ cn: () => "" }));
vi.mock("@/hooks/store/use-instance", () => ({
  useInstance: () => ({ config: { is_google_calendar_capacity_enabled: state.enabled } }),
}));
vi.mock("@/hooks/store/use-app-theme", () => ({ useAppTheme: () => ({}) }));
vi.mock("@/hooks/store/user", () => ({
  useUserPermissions: () => ({ allowPermissions: (roles: number[]) => roles.includes(state.role) }),
}));
vi.mock("@/hooks/use-local-storage", () => ({ default: () => ({ storedValue: true }) }));
vi.mock("@/hooks/use-navigation-preferences", () => ({
  usePersonalNavigationPreferences: () => ({ preferences: { items: {} } }),
  useWorkspaceNavigationPreferences: () => ({ preferences: { items: {} } }),
}));
vi.mock("@/components/sidebar/sidebar-navigation", () => ({
  SidebarNavItem: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
}));
vi.mock("@/components/workspace/upgrade-badge", () => ({ UpgradeBadge: () => null }));
vi.mock("./sidebar-item", () => ({ SidebarItemBase: () => null }));

import { SidebarMenuItems } from "./sidebar-menu-items";

describe("capacity links in the active workspace menu", () => {
  it.each([EUserWorkspaceRoles.MEMBER, EUserWorkspaceRoles.ADMIN])(
    "shows all capacity destinations for workspace role %s",
    (role) => {
      state.enabled = true;
      state.role = role;
      const html = renderToStaticMarkup(<SidebarMenuItems />);
      for (const [suffix, label] of [
        ["", "My capacity"],
        ["team/", "Team capacity"],
        ["planner/", "Workshop planner"],
      ]) {
        expect(html).toContain(`href="/test-workspace/capacity/${suffix}"`);
        expect(html).toContain(label);
      }
    }
  );

  it.each([false, undefined])("hides capacity when the feature flag is %s", (enabled) => {
    state.enabled = enabled;
    state.role = EUserWorkspaceRoles.ADMIN;
    expect(renderToStaticMarkup(<SidebarMenuItems />)).not.toContain("/capacity/");
  });

  it.each([EUserWorkspaceRoles.GUEST])("hides capacity from workspace role %s", (role) => {
    state.enabled = true;
    state.role = role;
    expect(renderToStaticMarkup(<SidebarMenuItems />)).not.toContain("/capacity/");
  });
});
