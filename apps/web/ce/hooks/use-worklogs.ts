/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import useSWR from "swr";
import { worklogService } from "@/plane-web/services/worklog.service";

export function useWorklogs(workspaceSlug: string, projectId: string, issueId: string, enabled: boolean = true) {
  const { data, isLoading, mutate } = useSWR(
    enabled && workspaceSlug && projectId && issueId ? `ISSUE_WORKLOGS_${workspaceSlug}_${projectId}_${issueId}` : null,
    () => worklogService.getWorklogs(workspaceSlug, projectId, issueId),
    { revalidateOnFocus: false }
  );

  return {
    worklogs: data?.worklogs ?? [],
    totalDuration: data?.total_duration ?? 0,
    isLoading,
    mutate,
  };
}
