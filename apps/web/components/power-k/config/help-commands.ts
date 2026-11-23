/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { ChatOutline, DocumentationOutline, Github, RocketOutline } from "@makeplane/propel/icons";
import { DOCUMENTATION_URL, ISSUE_TRACKER_URL, SOURCE_CODE_URL } from "@plane/constants";
// components
import type { TPowerKCommandConfig } from "@/components/power-k/core/types";
// helpers
import { showExternalLinks } from "@/helpers/external-links";
// hooks
import { useInstance } from "@/hooks/store/use-instance";
import { usePowerK } from "@/hooks/store/use-power-k";

/**
 * Help commands - Help related commands
 */
export const usePowerKHelpCommands = (): TPowerKCommandConfig[] => {
  // store
  const { toggleShortcutsListModal } = usePowerK();
  const { config } = useInstance();
  const product = config?.product;
  // Fork: the documentation and issue-tracker hosts are outbound links, so they follow the
  // operator's switch like the sidebar help menu. The source offer (AGPL section 13) stays.
  const linksAllowed = showExternalLinks(config);

  return [
    {
      id: "open_keyboard_shortcuts",
      type: "action",
      group: "help",
      i18n_title: "power_k.help_actions.open_keyboard_shortcuts",
      icon: RocketOutline,
      modifierShortcut: "cmd+/",
      action: () => toggleShortcutsListModal(true),
      isEnabled: () => true,
      isVisible: () => true,
      closeOnSelect: true,
    },
    {
      id: "open_plane_documentation",
      type: "action",
      group: "help",
      i18n_title: "power_k.help_actions.open_plane_documentation",
      icon: DocumentationOutline,
      action: () => {
        window.open(product?.documentation_url ?? DOCUMENTATION_URL, "_blank", "noopener,noreferrer");
      },
      isEnabled: () => linksAllowed,
      isVisible: () => linksAllowed,
      closeOnSelect: true,
    },
    {
      id: "join_forum",
      type: "action",
      group: "help",
      i18n_title: "power_k.help_actions.join_forum",
      icon: ChatOutline,
      action: () => {
        window.open(product?.source_url ?? SOURCE_CODE_URL, "_blank", "noopener,noreferrer");
      },
      isEnabled: () => true,
      isVisible: () => true,
      closeOnSelect: true,
    },
    {
      id: "report_bug",
      type: "action",
      group: "help",
      i18n_title: "power_k.help_actions.report_bug",
      icon: Github,
      action: () => {
        window.open(product?.issues_url ?? ISSUE_TRACKER_URL, "_blank", "noopener,noreferrer");
      },
      isEnabled: () => linksAllowed,
      isVisible: () => linksAllowed,
      closeOnSelect: true,
    },
  ];
};
