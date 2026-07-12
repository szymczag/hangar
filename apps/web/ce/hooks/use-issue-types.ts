/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import useSWR from "swr";
import { issueTypeService } from "@/plane-web/services/issue-type.service";
import type { TIssueTypeExt } from "@/plane-web/types/issue-types";

export const getIssueTypesKey = (workspaceSlug: string, projectId: string) =>
  `ISSUE_TYPES_${workspaceSlug}_${projectId}`;

/** Project issue types with their properties, SWR-cached. */
export const useIssueTypes = (workspaceSlug: string | undefined, projectId: string | undefined | null) => {
  const { data, isLoading, mutate } = useSWR<TIssueTypeExt[]>(
    workspaceSlug && projectId ? getIssueTypesKey(workspaceSlug, projectId) : null,
    workspaceSlug && projectId ? () => issueTypeService.getIssueTypes(workspaceSlug, projectId) : null,
    { revalidateOnFocus: false }
  );

  const getTypeById = (typeId: string | null | undefined) => data?.find((type) => type.id === typeId);
  const activeProperties = (typeId: string | null | undefined) =>
    (getTypeById(typeId)?.properties ?? []).filter((property) => property.is_active);

  return { issueTypes: data, isLoading, mutate, getTypeById, activeProperties };
};
