/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
// ui
import { Button } from "@makeplane/propel/components/button";
import { Tooltip } from "@makeplane/propel/components/tooltip";
import { useTranslation } from "@plane/i18n";
// hooks
import { useInstance } from "@/hooks/store/use-instance";
import { usePlatformOS } from "@/hooks/use-platform-os";
import packageJson from "package.json";
// Hangar extension
import { HANGAR_EDITION_NAME, HangarCommunityModal } from "@/plane-web/components/license/modal/community-modal";

export const WorkspaceEditionBadge = observer(function WorkspaceEditionBadge() {
  // states
  const [isCommunityModalOpen, setIsCommunityModalOpen] = useState(false);
  // translation
  const { t } = useTranslation();
  // platform
  const { isMobile } = usePlatformOS();
  // instance
  const { config } = useInstance();

  // `packageJson.version` is the upstream package's, not this fork's -- it is
  // only a fallback for a build the API has not answered for yet.
  const version = config?.product?.version ?? packageJson.version;

  return (
    <>
      <HangarCommunityModal isOpen={isCommunityModalOpen} handleClose={() => setIsCommunityModalOpen(false)} />
      {/* No hover tooltip on touch screens, where it would only cover the dialog it opens. */}
      <Tooltip label={`Version: ${version}`} disabled={isMobile}>
        <Button
          variant="tertiary"
          size="md"
          stretch="auto"
          label={HANGAR_EDITION_NAME}
          onClick={() => setIsCommunityModalOpen(true)}
          aria-haspopup="dialog"
          aria-label={t("aria_labels.projects_sidebar.edition_badge")}
        />
      </Tooltip>
    </>
  );
});
