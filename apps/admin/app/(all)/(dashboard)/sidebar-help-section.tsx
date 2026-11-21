/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import {
  DOCUMENTATION_URL,
  ISSUE_TRACKER_URL,
  SECURITY_REPORT_URL,
  SOURCE_CODE_URL,
  WEB_BASE_URL,
} from "@plane/constants";
import { useTranslation } from "@plane/i18n";
// plane internal packages
import { Button } from "@makeplane/propel/components/button";
import { Icon } from "@makeplane/propel/components/icon";
import { IconButton } from "@makeplane/propel/components/icon-button";
import { Menu, MenuContent, MenuFooter, MenuLinkItem, MenuTrigger } from "@makeplane/propel/components/menu";
import { Tooltip } from "@makeplane/propel/components/tooltip";
import {
  ArrowNarrowLeftOutline,
  CodeOutline,
  Github,
  HelpOutline,
  NewTabOutline,
  PagesOutline,
  ShieldOutline,
} from "@makeplane/propel/icons";
import { cn } from "@plane/utils";
// hooks
import { useInstance, useTheme } from "@/hooks/store";
// assets

export const AdminSidebarHelpSection = observer(function AdminSidebarHelpSection() {
  // plane hooks
  const { t } = useTranslation();
  // store
  const { instance, config } = useInstance();
  const product = config?.product;
  const { isSidebarCollapsed, toggleSidebar } = useTheme();

  const redirectionLink = encodeURI(WEB_BASE_URL + "/");
  const helpOptions = [
    {
      name: "Documentation",
      href: product?.documentation_url ?? DOCUMENTATION_URL,
      Icon: PagesOutline,
    },
    {
      name: "Open a GitHub issue",
      href: product?.issues_url ?? ISSUE_TRACKER_URL,
      Icon: Github,
    },
    {
      name: "Report a vulnerability privately",
      href: product?.security_url ?? SECURITY_REPORT_URL,
      Icon: ShieldOutline,
    },
    {
      name: "Source code and license",
      href: product?.source_url ?? SOURCE_CODE_URL,
      Icon: CodeOutline,
    },
  ];
  const version = product?.version ?? instance?.current_version ?? "development";
  const toggleSidebarLabel = isSidebarCollapsed
    ? t("aria_labels.projects_sidebar.expand_sidebar")
    : t("aria_labels.projects_sidebar.collapse_sidebar");

  return (
    <div
      className={cn("flex w-full shrink-0 items-center gap-1 border-t border-subtle px-3 py-3", {
        "flex-col": isSidebarCollapsed,
      })}
    >
      {isSidebarCollapsed ? (
        <Tooltip label="Open Hangar" side="right">
          <IconButton
            variant="secondary"
            size="md"
            aria-label="Open Hangar"
            showTooltip={false}
            nativeButton={false}
            render={<a href={redirectionLink} aria-label="Open Hangar" />}
            icon={<Icon icon={NewTabOutline} />}
          />
        </Tooltip>
      ) : (
        <Button
          variant="secondary"
          size="sm"
          stretch="auto"
          nativeButton={false}
          render={<a href={redirectionLink} aria-label="Open Hangar" />}
          icon={<Icon icon={NewTabOutline} />}
          label="Open Hangar"
        />
      )}
      <div className={cn("flex items-center gap-1", isSidebarCollapsed ? "flex-col" : "ml-auto")}>
        <Menu modal={false}>
          <Tooltip label="Help" side={isSidebarCollapsed ? "right" : "top"}>
            <MenuTrigger
              render={
                <IconButton
                  type="button"
                  variant="ghost"
                  size="md"
                  aria-label="Help"
                  showTooltip={false}
                  icon={<Icon icon={HelpOutline} />}
                />
              }
            />
          </Tooltip>
          <MenuContent
            side={isSidebarCollapsed ? "right" : "top"}
            align="end"
            footer={<MenuFooter>Hangar {version}</MenuFooter>}
          >
            {helpOptions.map(({ name, Icon: HelpIcon, href }) => (
              <MenuLinkItem
                key={name}
                href={href}
                external
                target="_blank"
                label={name}
                icon={<Icon icon={HelpIcon} tint="secondary" />}
              />
            ))}
          </MenuContent>
        </Menu>
        <Tooltip label={toggleSidebarLabel} side={isSidebarCollapsed ? "right" : "top"}>
          <IconButton
            type="button"
            variant="ghost"
            size="md"
            aria-label={toggleSidebarLabel}
            aria-expanded={!isSidebarCollapsed}
            aria-controls="admin-sidebar"
            showTooltip={false}
            icon={
              <Icon
                icon={
                  <ArrowNarrowLeftOutline
                    className={cn("size-4 duration-300 motion-reduce:transition-none", {
                      "rotate-180": isSidebarCollapsed,
                    })}
                  />
                }
              />
            }
            onClick={() => toggleSidebar(!isSidebarCollapsed)}
          />
        </Tooltip>
      </div>
    </div>
  );
});
