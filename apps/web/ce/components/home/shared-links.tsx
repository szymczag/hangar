/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { Button } from "@makeplane/propel/components/button";
import { HideOutline, NewTabOutline, ShowOutline } from "@makeplane/propel/icons";
import type { TContextMenuItem } from "@plane/blocks/context-menu";
import { useTranslation } from "@plane/i18n";
import type { TWorkspaceSharedLink } from "@plane/services";
import { cn } from "@plane/utils";
// components
import { LinkItemBlock } from "@/components/home/widgets/links/link-item-block";
// hooks
import { useWorkspaceSharedLinks } from "@/plane-web/hooks/use-workspace-shared-links";

type Props = {
  workspaceSlug: string;
};

const openInNewTab = (url: string) => window.open(url, "_blank", "noopener,noreferrer");

/**
 * The quick links a workspace admin gives everyone.
 *
 * Rendered as its own group above the personal ones, because they are not the
 * reader's to edit -- the only thing they may do is take one off their own home
 * page, and put it back. With no shared links this renders nothing and the
 * widget looks exactly as it did before.
 *
 * Each link is upstream's quick link card, so the two groups look alike; its
 * menu offers opening the link and hiding it, nothing that would edit it.
 */
export const WorkspaceSharedLinks = ({ workspaceSlug }: Props) => {
  const { visibleLinks, hiddenLinks, setHidden, isLoading } = useWorkspaceSharedLinks(workspaceSlug);
  const [showingHidden, setShowingHidden] = useState(false);
  const { t } = useTranslation();

  if (isLoading || (visibleLinks.length === 0 && hiddenLinks.length === 0)) return null;

  const shown = showingHidden ? [...visibleLinks, ...hiddenLinks] : visibleLinks;

  const menuItems = (link: TWorkspaceSharedLink): TContextMenuItem[] => [
    {
      key: "open-new-tab",
      action: () => openInNewTab(link.url),
      title: t("open_in_new_tab"),
      icon: NewTabOutline,
    },
    {
      key: link.is_hidden ? "show" : "hide",
      action: () => void setHidden(link.id, !link.is_hidden),
      title: link.is_hidden
        ? t("workspace_settings.settings.home_defaults.show_hidden")
        : t("workspace_settings.settings.home_defaults.hide"),
      icon: link.is_hidden ? ShowOutline : HideOutline,
    },
  ];

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <span className="text-body-xs-medium text-tertiary">
          {t("workspace_settings.settings.home_defaults.shared_links")}
        </span>
        {hiddenLinks.length > 0 && (
          <Button
            variant="ghost"
            size="sm"
            stretch="auto"
            type="button"
            label={
              showingHidden
                ? t("common.cancel")
                : `${t("workspace_settings.settings.home_defaults.show_hidden")} (${hiddenLinks.length})`
            }
            onClick={() => setShowingHidden((current) => !current)}
          />
        )}
      </div>

      <ul className="grid w-full grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {shown.map((link) => (
          <li key={link.id} className={cn(link.is_hidden && "opacity-60")}>
            <LinkItemBlock
              title={link.title || link.url}
              url={link.url}
              menuItems={menuItems(link)}
              onClick={() => openInNewTab(link.url)}
            />
          </li>
        ))}
      </ul>
    </div>
  );
};
