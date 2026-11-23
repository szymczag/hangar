/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React, { useMemo } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import { Collapsible } from "@makeplane/propel/components/collapsible";
import {
  AnalyticsOutline,
  CalendarLayoutOutline,
  ClockOutline,
  ImportsOutline,
  MembersOutline,
  MoreHorizontalOutline,
} from "@makeplane/propel/icons";
// plane imports
import {
  WORKSPACE_SIDEBAR_DYNAMIC_NAVIGATION_ITEMS_LINKS,
  WORKSPACE_SIDEBAR_STATIC_NAVIGATION_ITEMS,
  WORKSPACE_SIDEBAR_STATIC_NAVIGATION_ITEMS_LINKS,
  WORKSPACE_SIDEBAR_STATIC_PINNED_NAVIGATION_ITEMS_LINKS,
} from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { EUserWorkspaceRoles } from "@plane/types";
// components
import { ListItem, ListItemLabel } from "@makeplane/propel/components/list";
import { ListItemButton } from "@makeplane/propel/elements/list";
// store hooks
import { useInstance } from "@/hooks/store/use-instance";
import { useAppTheme } from "@/hooks/store/use-app-theme";
import useLocalStorage from "@/hooks/use-local-storage";
import {
  usePersonalNavigationPreferences,
  useWorkspaceNavigationPreferences,
} from "@/hooks/use-navigation-preferences";
import { SidebarItemBase } from "./sidebar-item";
import { SidebarWorkspaceMenuItem } from "./workspace-menu-item";

export const SidebarMenuItems = observer(function SidebarMenuItems() {
  // routers
  const { workspaceSlug } = useParams();
  const { config } = useInstance();
  const { setValue: toggleWorkspaceMenu, storedValue: isWorkspaceMenuOpen } = useLocalStorage<boolean>(
    "is_workspace_menu_open",
    true
  );

  // store hooks
  const { isExtendedSidebarOpened, toggleExtendedSidebar } = useAppTheme();
  // hooks
  const { preferences: personalPreferences } = usePersonalNavigationPreferences();
  const { preferences: workspacePreferences } = useWorkspaceNavigationPreferences();
  // translation
  const { t } = useTranslation();

  const toggleListDisclosure = (isOpen: boolean) => {
    toggleWorkspaceMenu(isOpen);
  };

  // Filter static navigation items based on personal preferences
  const filteredStaticNavigationItems = useMemo(() => {
    const items = [...WORKSPACE_SIDEBAR_STATIC_NAVIGATION_ITEMS_LINKS];
    const personalItems: Array<(typeof items)[0] & { sort_order: number }> = [];

    // Add personal items based on preferences with their sort_order
    const stickiesItem = WORKSPACE_SIDEBAR_STATIC_NAVIGATION_ITEMS["stickies"];
    if (personalPreferences.items.stickies?.enabled && stickiesItem) {
      personalItems.push({
        ...stickiesItem,
        sort_order: personalPreferences.items.stickies.sort_order,
      });
    }
    if (personalPreferences.items.your_work?.enabled && WORKSPACE_SIDEBAR_STATIC_NAVIGATION_ITEMS["your-work"]) {
      personalItems.push({
        ...WORKSPACE_SIDEBAR_STATIC_NAVIGATION_ITEMS["your-work"],
        sort_order: personalPreferences.items.your_work.sort_order,
      });
    }
    if (personalPreferences.items.drafts?.enabled && WORKSPACE_SIDEBAR_STATIC_NAVIGATION_ITEMS["drafts"]) {
      personalItems.push({
        ...WORKSPACE_SIDEBAR_STATIC_NAVIGATION_ITEMS["drafts"],
        sort_order: personalPreferences.items.drafts.sort_order,
      });
    }

    // Sort personal items by sort_order
    personalItems.sort((a, b) => a.sort_order - b.sort_order);

    // Merge static items with sorted personal items
    return [...items, ...personalItems];
  }, [personalPreferences]);

  const sortedNavigationItems = useMemo(
    () =>
      // oxlint-disable-next-line oxc/no-map-spread
      WORKSPACE_SIDEBAR_DYNAMIC_NAVIGATION_ITEMS_LINKS.map((item) => {
        const preference = workspacePreferences.items[item.key];
        return {
          ...item,
          sort_order: preference ? preference.sort_order : 0,
        };
      }).sort((a, b) => a.sort_order - b.sort_order),
    [workspacePreferences]
  );

  const capacityNavigationItems = [
    {
      key: "capacity-personal",
      label: "My capacity",
      labelTranslationKey: "",
      href: `/${workspaceSlug}/capacity/`,
      access: [EUserWorkspaceRoles.ADMIN, EUserWorkspaceRoles.MEMBER],
      Icon: ClockOutline,
    },
    {
      key: "capacity-team",
      label: "Team capacity",
      labelTranslationKey: "",
      href: `/${workspaceSlug}/capacity/team/`,
      access: [EUserWorkspaceRoles.ADMIN, EUserWorkspaceRoles.MEMBER],
      Icon: MembersOutline,
    },
    {
      key: "capacity-planner",
      label: "Workshop planner",
      labelTranslationKey: "",
      href: `/${workspaceSlug}/capacity/planner/`,
      access: [EUserWorkspaceRoles.ADMIN, EUserWorkspaceRoles.MEMBER],
      Icon: CalendarLayoutOutline,
    },
    {
      key: "capacity-reports",
      label: "Training report",
      labelTranslationKey: "",
      href: `/${workspaceSlug}/capacity/reports/`,
      access: [EUserWorkspaceRoles.ADMIN, EUserWorkspaceRoles.MEMBER],
      Icon: AnalyticsOutline,
    },
    {
      // Administrator-only: the listing carries calendar titles, which the rest
      // of the product deliberately does not show.
      key: "capacity-imports",
      label: "Import from calendar",
      labelTranslationKey: "",
      href: `/${workspaceSlug}/capacity/imports/`,
      access: [EUserWorkspaceRoles.ADMIN],
      Icon: ImportsOutline,
    },
  ];

  return (
    <>
      <div className="flex w-full flex-col gap-px">
        {filteredStaticNavigationItems.map((item, _index) => (
          // oxlint-disable-next-line react/no-array-index-key
          <SidebarItemBase key={`static_${_index}`} item={item} />
        ))}
      </div>
      <Collapsible
        placement="sidebar"
        open={!!isWorkspaceMenuOpen}
        onOpenChange={toggleListDisclosure}
        trigger={<span className="text-body-xs-semibold whitespace-nowrap text-tertiary">{t("common.workspace")}</span>}
      >
        <div className="flex w-full flex-col gap-px">
          {WORKSPACE_SIDEBAR_STATIC_PINNED_NAVIGATION_ITEMS_LINKS.map((item, _index) => (
            // oxlint-disable-next-line react/no-array-index-key
            <SidebarItemBase key={`static_${_index}`} item={item} />
          ))}
          {sortedNavigationItems.map((item, _index) => (
            // oxlint-disable-next-line react/no-array-index-key
            <SidebarItemBase key={`dynamic_${_index}`} item={item} />
          ))}
          {config?.is_google_calendar_capacity_enabled === true &&
            capacityNavigationItems.map((item) => <SidebarWorkspaceMenuItem key={item.key} item={item} />)}
          <ListItem density="comfortable">
            <ListItemButton
              type="button"
              onClick={() => toggleExtendedSidebar()}
              id="extended-sidebar-toggle"
              aria-label={t(
                isExtendedSidebarOpened
                  ? "aria_labels.projects_sidebar.close_extended_sidebar"
                  : "aria_labels.projects_sidebar.open_extended_sidebar"
              )}
            >
              <MoreHorizontalOutline className="size-4 flex-shrink-0" />
              <ListItemLabel>{isExtendedSidebarOpened ? t("sidebar.hide") : t("sidebar.more")}</ListItemLabel>
            </ListItemButton>
          </ListItem>
        </div>
      </Collapsible>
    </>
  );
});
