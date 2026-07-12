/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { IProjectIssues } from "@/store/issue/project";
import { ProjectIssues } from "@/store/issue/project";
import type { IIssueRootStore } from "@/store/issue/root.store";
import { EIssueServiceType } from "@plane/types";
import type { IProjectEpicsFilter } from "./filter.store";

export type IProjectEpics = IProjectIssues;

export class ProjectEpics extends ProjectIssues implements IProjectEpics {
  constructor(_rootStore: IIssueRootStore, issueFilterStore: IProjectEpicsFilter) {
    super(_rootStore, issueFilterStore, EIssueServiceType.EPICS);
  }
}
