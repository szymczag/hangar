/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { IProjectIssuesFilter } from "@/store/issue/project";
import { ProjectIssuesFilter } from "@/store/issue/project";
import type { IIssueRootStore } from "@/store/issue/root.store";
import { EIssuesStoreType } from "@plane/types";
import { IssueFiltersService } from "@/services/issue_filter.service";

export type IProjectEpicsFilter = IProjectIssuesFilter;

export class ProjectEpicsFilter extends ProjectIssuesFilter implements IProjectEpicsFilter {
  constructor(_rootStore: IIssueRootStore) {
    super(_rootStore);
    const epicFilterService = new IssueFiltersService();
    this.projectService = {
      getProjectUserProperties: (workspaceSlug: string, projectId: string) =>
        epicFilterService.fetchProjectEpicFilters(workspaceSlug, projectId),
      updateProjectUserProperties: (
        workspaceSlug: string,
        projectId: string,
        data: Parameters<IssueFiltersService["patchProjectEpicFilters"]>[2]
      ) => epicFilterService.patchProjectEpicFilters(workspaceSlug, projectId, data),
    };
  }

  protected override get issuesStore() {
    return this.rootIssueStore.projectEpics;
  }

  protected override get issuesStoreType() {
    return EIssuesStoreType.EPIC;
  }
}
