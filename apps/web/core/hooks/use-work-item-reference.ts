/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useContext, useEffect } from "react";
import type { TIssue } from "@plane/types";
import { createWorkItemReferenceBatcher } from "@/helpers/work-item-reference-batcher";
import { StoreContext } from "@/lib/store-context";

type TIssuesStore = { getIssues: (workspaceSlug: string, projectId: string, issueIds: string[]) => Promise<TIssue[]> };

// A list page references parents and epics that are often not part of the page
// that was loaded (sub-work items hidden, another group, another page). They are
// fetched through the permission-scoped work item list endpoint, so a guest never
// receives a work item they could not open directly.
let requestReference: ReturnType<typeof createWorkItemReferenceBatcher> | undefined;
let requestReferenceStore: TIssuesStore | undefined;

const getReferenceRequester = (issuesStore: TIssuesStore) => {
  if (!requestReference || requestReferenceStore !== issuesStore) {
    requestReference = createWorkItemReferenceBatcher(issuesStore.getIssues);
    requestReferenceStore = issuesStore;
  }
  return requestReference;
};

/** Resolve a referenced work item (such as a parent) from the store, fetching it once when missing. */
export const useWorkItemReference = (
  workspaceSlug: string | undefined,
  projectId: string | null | undefined,
  workItemId: string | null | undefined
): TIssue | undefined => {
  const context = useContext(StoreContext);
  if (context === undefined) throw new Error("useWorkItemReference must be used within StoreProvider");
  const issuesStore = context.issue.issues;
  const workItem = workItemId ? issuesStore.getIssueById(workItemId) : undefined;

  useEffect(() => {
    if (workItem || !workspaceSlug || !projectId || !workItemId) return;
    getReferenceRequester(issuesStore)(workspaceSlug, projectId, workItemId);
  }, [workItem, workspaceSlug, projectId, workItemId, issuesStore]);

  return workItem;
};
