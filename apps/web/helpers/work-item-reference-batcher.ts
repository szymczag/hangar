/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export const MAX_REFERENCE_IDS_PER_REQUEST = 100;

type TFetchReferences = (workspaceSlug: string, projectId: string, workItemIds: string[]) => Promise<unknown>;
type TSchedule = (callback: () => void) => unknown;

/**
 * Collect work item references per project and fetch each once, in batches.
 *
 * Every identifier is requested at most once for the batcher's lifetime, so a
 * reference the viewer cannot access is not retried on every render.
 */
export const createWorkItemReferenceBatcher = (
  fetchReferences: TFetchReferences,
  schedule: TSchedule = (callback) => setTimeout(callback, 0)
) => {
  const requested = new Set<string>();
  const pending = new Map<string, { workspaceSlug: string; projectId: string; ids: Set<string> }>();
  let isScheduled = false;

  const flush = () => {
    isScheduled = false;
    const batches = Array.from(pending.values());
    pending.clear();
    for (const { workspaceSlug, projectId, ids } of batches) {
      const workItemIds = Array.from(ids);
      for (let start = 0; start < workItemIds.length; start += MAX_REFERENCE_IDS_PER_REQUEST) {
        fetchReferences(
          workspaceSlug,
          projectId,
          workItemIds.slice(start, start + MAX_REFERENCE_IDS_PER_REQUEST)
        ).catch(() => {
          // Unresolved references render without details.
        });
      }
    }
  };

  return (workspaceSlug: string, projectId: string, workItemId: string) => {
    const referenceKey = `${projectId}:${workItemId}`;
    if (requested.has(referenceKey)) return;
    requested.add(referenceKey);

    const batchKey = `${workspaceSlug}:${projectId}`;
    const batch = pending.get(batchKey) ?? { workspaceSlug, projectId, ids: new Set<string>() };
    batch.ids.add(workItemId);
    pending.set(batchKey, batch);

    if (!isScheduled) {
      isScheduled = true;
      schedule(flush);
    }
  };
};
