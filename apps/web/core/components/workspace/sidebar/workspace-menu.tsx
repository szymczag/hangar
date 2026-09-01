/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import { Disclosure, Transition } from "@headlessui/react";
// plane imports
import { AnalyticsIcon, CycleIcon, ProjectIcon, ViewsIcon } from "@plane/propel/icons";
import { CalendarClock } from "lucide-react";
import { EUserWorkspaceRoles } from "@plane/types";
// hooks
import useLocalStorage from "@/hooks/use-local-storage";
import { useInstance } from "@/hooks/store/use-instance";
// local imports
import { SidebarWorkspaceMenuHeader } from "./workspace-menu-header";
import { SidebarWorkspaceMenuItem } from "./workspace-menu-item";

export const SidebarWorkspaceMenu = observer(function SidebarWorkspaceMenu() {
  // router params
  const { workspaceSlug } = useParams();
  const { config } = useInstance();
  // local storage
  const { setValue: toggleWorkspaceMenu, storedValue } = useLocalStorage<boolean>("is_workspace_menu_open", true);
  // derived values
  const isWorkspaceMenuOpen = !!storedValue;

  const SIDEBAR_WORKSPACE_MENU_ITEMS = [
    {
      key: "projects",
      labelTranslationKey: "sidebar.projects",
      href: `/${workspaceSlug}/projects/`,
      access: [EUserWorkspaceRoles.ADMIN, EUserWorkspaceRoles.MEMBER, EUserWorkspaceRoles.GUEST],
      Icon: ProjectIcon,
    },
    {
      key: "views",
      labelTranslationKey: "sidebar.views",
      href: `/${workspaceSlug}/workspace-views/all-issues/`,
      access: [EUserWorkspaceRoles.ADMIN, EUserWorkspaceRoles.MEMBER, EUserWorkspaceRoles.GUEST],
      Icon: ViewsIcon,
    },
    {
      key: "active-cycles",
      labelTranslationKey: "sidebar.cycles",
      href: `/${workspaceSlug}/active-cycles/`,
      access: [EUserWorkspaceRoles.ADMIN, EUserWorkspaceRoles.MEMBER],
      Icon: CycleIcon,
    },
    {
      key: "capacity",
      label: "Trainer capacity",
      labelTranslationKey: "",
      href: `/${workspaceSlug}/capacity/`,
      access: [EUserWorkspaceRoles.ADMIN, EUserWorkspaceRoles.MEMBER],
      Icon: CalendarClock,
    },
    {
      key: "analytics",
      labelTranslationKey: "sidebar.analytics",
      href: `/${workspaceSlug}/analytics/`,
      access: [EUserWorkspaceRoles.ADMIN, EUserWorkspaceRoles.MEMBER],
      Icon: AnalyticsIcon,
    },
  ];

  return (
    <Disclosure as="div" defaultOpen>
      <SidebarWorkspaceMenuHeader isWorkspaceMenuOpen={isWorkspaceMenuOpen} toggleWorkspaceMenu={toggleWorkspaceMenu} />
      <Transition
        show={isWorkspaceMenuOpen}
        enter="transition duration-100 ease-out"
        enterFrom="transform scale-95 opacity-0"
        enterTo="transform scale-100 opacity-100"
        leave="transition duration-75 ease-out"
        leaveFrom="transform scale-100 opacity-100"
        leaveTo="transform scale-95 opacity-0"
      >
        <Disclosure.Panel as="div" className="mt-0.5 flex flex-col gap-0.5" static>
          {SIDEBAR_WORKSPACE_MENU_ITEMS.filter(
            (item) => item.key !== "capacity" || config?.is_google_calendar_capacity_enabled === true
          ).map((item) => (
            <SidebarWorkspaceMenuItem key={item.key} item={item} />
          ))}
        </Disclosure.Panel>
      </Transition>
    </Disclosure>
  );
});
