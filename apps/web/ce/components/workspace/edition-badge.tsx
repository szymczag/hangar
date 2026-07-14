/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
// ui
import { useTranslation } from "@plane/i18n";
import { Tooltip } from "@plane/propel/tooltip";
// hooks
import { usePlatformOS } from "@/hooks/use-platform-os";
import packageJson from "package.json";
// local components
import { HangarCommunityModal } from "../license";
import { Button } from "@plane/propel/button";

export const WorkspaceEditionBadge = observer(function WorkspaceEditionBadge() {
  // states
  const [isCommunityModalOpen, setIsCommunityModalOpen] = useState(false);
  // translation
  const { t } = useTranslation();
  // platform
  const { isMobile } = usePlatformOS();

  return (
    <>
      <HangarCommunityModal isOpen={isCommunityModalOpen} handleClose={() => setIsCommunityModalOpen(false)} />
      <Tooltip tooltipContent={`Version: v${packageJson.version}`} isMobile={isMobile}>
        <Button
          variant="tertiary"
          size="lg"
          onClick={() => setIsCommunityModalOpen(true)}
          aria-haspopup="dialog"
          aria-label={t("aria_labels.projects_sidebar.edition_badge")}
        >
          Hangar Community
        </Button>
      </Tooltip>
    </>
  );
});
