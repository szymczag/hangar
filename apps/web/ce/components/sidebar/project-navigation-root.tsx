/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Fork (see FORK.md): adds the Epics entry to the project navigation.

import { Layers } from "lucide-react";
import { EUserPermissions } from "@plane/constants";
// components
import type { TNavigationItem } from "@/components/workspace/sidebar/project-navigation";
import { ProjectNavigation } from "@/components/workspace/sidebar/project-navigation";

type TProjectItemsRootProps = {
  workspaceSlug: string;
  projectId: string;
};

const getEpicNavigationItems = (workspaceSlug: string, projectId: string): TNavigationItem[] => [
  {
    name: "Epics",
    href: `/${workspaceSlug}/projects/${projectId}/epics`,
    icon: Layers,
    access: [EUserPermissions.ADMIN, EUserPermissions.MEMBER, EUserPermissions.GUEST],
    shouldRender: true,
    sortOrder: 1.5,
    i18n_key: "common.epics",
    key: "epics",
  },
];

export function ProjectNavigationRoot(props: TProjectItemsRootProps) {
  const { workspaceSlug, projectId } = props;
  return (
    <ProjectNavigation
      workspaceSlug={workspaceSlug}
      projectId={projectId}
      additionalNavigationItems={getEpicNavigationItems}
    />
  );
}
