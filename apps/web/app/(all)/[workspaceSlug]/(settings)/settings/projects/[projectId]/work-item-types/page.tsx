/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// plane imports
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
// components
import { NotAuthorizedView } from "@/components/auth-screens/not-authorized-view";
import { PageHead } from "@/components/core/page-title";
import { SettingsContentWrapper } from "@/components/settings/content-wrapper";
// hooks
import { useProject } from "@/hooks/store/use-project";
import { useUserPermissions } from "@/hooks/store/user";
// plane web
import { IssueTypesSettingsRoot } from "@/plane-web/components/issue-types/settings-root";
import type { Route } from "./+types/page";

function WorkItemTypesSettingsPage({ params }: Route.ComponentProps) {
  const { workspaceSlug, projectId } = params;
  // store hooks
  const { currentProjectDetails } = useProject();
  const { workspaceUserInfo, allowPermissions } = useUserPermissions();
  // derived values
  const pageTitle = currentProjectDetails?.name ? `${currentProjectDetails?.name} - Work item types` : undefined;
  const isAdmin = allowPermissions([EUserPermissions.ADMIN], EUserPermissionsLevel.PROJECT);
  const canView = allowPermissions([EUserPermissions.ADMIN, EUserPermissions.MEMBER], EUserPermissionsLevel.PROJECT);

  if (workspaceUserInfo && !canView) {
    return <NotAuthorizedView section="settings" isProjectView />;
  }

  return (
    <SettingsContentWrapper>
      <PageHead title={pageTitle} />
      <IssueTypesSettingsRoot workspaceSlug={workspaceSlug} projectId={projectId} isAdmin={isAdmin} />
    </SettingsContentWrapper>
  );
}

export default observer(WorkItemTypesSettingsPage);
