/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React from "react";
import { observer } from "mobx-react";
import { CodeOutline, Github, HelpOutline, PagesOutline, ShieldOutline } from "@makeplane/propel/icons";
import { DOCUMENTATION_URL, ISSUE_TRACKER_URL, SECURITY_REPORT_URL, SOURCE_CODE_URL } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
// ui
import { Icon } from "@makeplane/propel/components/icon";
import { Menu, MenuContent, MenuFooter, MenuItem, MenuSeparator, MenuTrigger } from "@makeplane/propel/components/menu";
import { Tooltip } from "@makeplane/propel/components/tooltip";
import { IconButton } from "@makeplane/propel/elements/icon-button";
// helpers
import { showExternalLinks } from "@/helpers/external-links";
// hooks
import { useInstance } from "@/hooks/store/use-instance";
import { usePowerK } from "@/hooks/store/use-power-k";

const openInNewTab = (url: string) => window.open(url, "_blank", "noopener,noreferrer");

export const HelpMenuRoot = observer(function HelpMenuRoot() {
  // store hooks
  const { t } = useTranslation();
  const { toggleShortcutsListModal } = usePowerK();
  const { config, instance } = useInstance();
  const product = config?.product;

  // This control opens links to documentation, issue-tracker and security
  // hosts, so remove the entry point when the operator disables outbound links.
  if (!showExternalLinks(config)) return null;

  return (
    <Menu>
      <Tooltip label={t("power_k.group_titles.help")} side="bottom">
        <MenuTrigger
          render={
            <IconButton
              variant="ghost"
              size="md"
              aria-label={t("power_k.group_titles.help")}
              render={<button type="button" className="data-popup-open:bg-layer-transparent-active" />}
            >
              <HelpOutline className="size-4.5" />
            </IconButton>
          }
        />
      </Tooltip>
      <MenuContent
        side="bottom"
        align="end"
        footer={<MenuFooter>Hangar {product?.version ?? instance?.current_version ?? "development"}</MenuFooter>}
      >
        <MenuItem
          icon={<Icon icon={PagesOutline} tint="secondary" />}
          label={t("documentation")}
          onClick={() => openInNewTab(product?.documentation_url ?? DOCUMENTATION_URL)}
        />
        <MenuItem
          icon={<Icon icon={Github} tint="secondary" />}
          label="Open a GitHub issue"
          onClick={() => openInNewTab(product?.issues_url ?? ISSUE_TRACKER_URL)}
        />
        <MenuItem
          icon={<Icon icon={ShieldOutline} tint="secondary" />}
          label="Report a vulnerability privately"
          onClick={() => openInNewTab(product?.security_url ?? SECURITY_REPORT_URL)}
        />
        <MenuSeparator />
        <MenuItem label={t("keyboard_shortcuts")} onClick={() => toggleShortcutsListModal(true)} />
        <MenuItem
          icon={<Icon icon={CodeOutline} tint="secondary" />}
          label="Source code and license"
          onClick={() => openInNewTab(product?.source_url ?? SOURCE_CODE_URL)}
        />
      </MenuContent>
    </Menu>
  );
});
