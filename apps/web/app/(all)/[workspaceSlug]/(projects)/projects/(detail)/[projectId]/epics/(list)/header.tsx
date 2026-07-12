/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import useSWR from "swr";
// plane imports
import { Button } from "@plane/propel/button";
import { Breadcrumbs, Header } from "@plane/ui";
// components
import { BreadcrumbLink } from "@/components/common/breadcrumb-link";
// hooks
import { useProject } from "@/hooks/store/use-project";
import { useUserPermissions } from "@/hooks/store/user";
// plane web
import { CreateUpdateEpicModal } from "@/plane-web/components/epics/epic-modal/modal";
import { epicService } from "@/plane-web/services/epic.service";
// plane imports
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";

export const ProjectEpicsHeader = observer(function ProjectEpicsHeader() {
  // router
  const { workspaceSlug, projectId } = useParams();
  // state
  const [isModalOpen, setIsModalOpen] = useState(false);
  // store hooks
  const { getProjectById } = useProject();
  const { allowPermissions } = useUserPermissions();
  // derived values
  const project = projectId ? getProjectById(projectId.toString()) : undefined;
  const workspaceSlugValue = workspaceSlug?.toString();
  const projectIdValue = projectId?.toString();
  const { data: epicSettings } = useSWR(
    workspaceSlugValue && projectIdValue ? `EPIC_SETTINGS_${workspaceSlugValue}_${projectIdValue}` : null,
    () => epicService.getSettings(workspaceSlugValue!, projectIdValue!),
    { revalidateOnFocus: false }
  );
  const canCreateEpic = allowPermissions(
    [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
    EUserPermissionsLevel.PROJECT,
    workspaceSlug?.toString(),
    projectId?.toString()
  );

  return (
    <>
      <CreateUpdateEpicModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} />
      <Header>
        <Header.LeftItem>
          <Breadcrumbs>
            <Breadcrumbs.Item
              component={
                <BreadcrumbLink
                  href={`/${workspaceSlug}/projects/${projectId}/issues`}
                  label={project?.name ?? "Project"}
                />
              }
            />
            <Breadcrumbs.Item component={<BreadcrumbLink label="Epics" />} />
          </Breadcrumbs>
        </Header.LeftItem>
        <Header.RightItem>
          {canCreateEpic && epicSettings?.is_epic_enabled && (
            <Button variant="primary" size="base" onClick={() => setIsModalOpen(true)}>
              Add epic
            </Button>
          )}
        </Header.RightItem>
      </Header>
    </>
  );
});
