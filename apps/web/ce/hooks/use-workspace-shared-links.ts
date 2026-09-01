/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import useSWR from "swr";
import { WorkspaceDefaultsService } from "@plane/services";
import type { TWorkspaceSharedLink } from "@plane/services";

const service = new WorkspaceDefaultsService();

/**
 * The quick links the workspace gives everyone.
 *
 * SWR rather than the MobX store on purpose: this list is read-only for almost
 * everyone, is not edited from the widget, and has no cross-component state to
 * keep in step. Putting it in the store would be ceremony without a payoff.
 */
export const useWorkspaceSharedLinks = (workspaceSlug: string | undefined) => {
  const { data, isLoading, mutate } = useSWR(
    workspaceSlug ? `WORKSPACE_SHARED_LINKS_${workspaceSlug}` : null,
    workspaceSlug ? () => service.listSharedLinks(workspaceSlug) : null,
    { revalidateOnFocus: false }
  );

  const links: TWorkspaceSharedLink[] = data ?? [];

  const setHidden = async (linkId: string, hidden: boolean) => {
    if (!workspaceSlug) return;
    // Optimistic: hiding a link is instant and reversible, so making someone
    // wait for a round trip to see it disappear would be the wrong trade.
    await mutate(
      async () => {
        await service.setSharedLinkHidden(workspaceSlug, linkId, hidden);
        return service.listSharedLinks(workspaceSlug);
      },
      {
        optimisticData: links.map((link) => (link.id === linkId ? { ...link, is_hidden: hidden } : link)),
        rollbackOnError: true,
        revalidate: false,
      }
    );
  };

  return {
    links,
    visibleLinks: links.filter((link) => !link.is_hidden),
    hiddenLinks: links.filter((link) => link.is_hidden),
    isLoading: Boolean(workspaceSlug) && isLoading,
    setHidden,
    mutate,
  };
};
