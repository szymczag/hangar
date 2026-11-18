/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React, { useState } from "react";
import { observer } from "mobx-react";
import { FileCode2, Github, HelpCircle, ShieldCheck } from "lucide-react";
import { DOCUMENTATION_URL, ISSUE_TRACKER_URL, SECURITY_REPORT_URL, SOURCE_CODE_URL } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { PageIcon } from "@plane/propel/icons";
// ui
import { CustomMenu } from "@plane/ui";
// components
import { AppSidebarItem } from "@/components/sidebar/sidebar-item";
// helpers
import { showExternalLinks } from "@/helpers/external-links";
// hooks
import { useInstance } from "@/hooks/store/use-instance";
import { usePowerK } from "@/hooks/store/use-power-k";

export const HelpMenuRoot = observer(function HelpMenuRoot() {
  // store hooks
  const { t } = useTranslation();
  const { toggleShortcutsListModal } = usePowerK();
  const { config, instance } = useInstance();
  const product = config?.product;
  // states
  const [isNeedHelpOpen, setIsNeedHelpOpen] = useState(false);

  // This control opens links to documentation, issue-tracker and security
  // hosts, so remove the entry point when the operator disables outbound links.
  if (!showExternalLinks(config)) return null;

  return (
    <>
      <CustomMenu
        customButton={
          <AppSidebarItem
            variant="button"
            item={{
              icon: <HelpCircle className="size-5" />,
              isActive: isNeedHelpOpen,
            }}
          />
        }
        // customButtonClassName="relative grid place-items-center rounded-md p-1.5 outline-none"
        menuButtonOnClick={() => !isNeedHelpOpen && setIsNeedHelpOpen(true)}
        onMenuClose={() => setIsNeedHelpOpen(false)}
        placement="bottom-end"
        maxHeight="lg"
        closeOnSelect
      >
        <CustomMenu.MenuItem
          onClick={() => window.open(product?.documentation_url ?? DOCUMENTATION_URL, "_blank", "noopener,noreferrer")}
        >
          <div className="flex items-center gap-x-2 rounded-sm text-11">
            <PageIcon className="h-3.5 w-3.5 text-secondary" height={14} width={14} />
            <span className="text-11">{t("documentation")}</span>
          </div>
        </CustomMenu.MenuItem>
        <CustomMenu.MenuItem
          onClick={() => window.open(product?.issues_url ?? ISSUE_TRACKER_URL, "_blank", "noopener,noreferrer")}
        >
          <div className="flex items-center gap-x-2 rounded-sm text-11">
            <Github className="h-3.5 w-3.5 text-secondary" size={14} />
            <span className="text-11">Open a GitHub issue</span>
          </div>
        </CustomMenu.MenuItem>
        <CustomMenu.MenuItem
          onClick={() => window.open(product?.security_url ?? SECURITY_REPORT_URL, "_blank", "noopener,noreferrer")}
        >
          <div className="flex items-center gap-x-2 rounded-sm text-11">
            <ShieldCheck className="h-3.5 w-3.5 text-secondary" size={14} />
            <span className="text-11">Report a vulnerability privately</span>
          </div>
        </CustomMenu.MenuItem>
        <div className="my-1 border-t border-subtle" />
        <CustomMenu.MenuItem>
          <button
            type="button"
            onClick={() => toggleShortcutsListModal(true)}
            className="flex w-full items-center hover:bg-layer-1"
          >
            <span className="text-11">{t("keyboard_shortcuts")}</span>
          </button>
        </CustomMenu.MenuItem>
        <CustomMenu.MenuItem
          onClick={() => window.open(product?.source_url ?? SOURCE_CODE_URL, "_blank", "noopener,noreferrer")}
        >
          <div className="flex items-center gap-x-2 rounded-sm text-11">
            <FileCode2 className="h-3.5 w-3.5 text-secondary" size={14} />
            <span className="text-11">Source code and license</span>
          </div>
        </CustomMenu.MenuItem>
        <div className="mt-1 border-t border-subtle px-1 pt-2 text-11 text-secondary">
          Hangar {product?.version ?? instance?.current_version ?? "development"}
        </div>
      </CustomMenu>
    </>
  );
});
