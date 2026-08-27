/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 */

import { createContext, type ReactNode, useContext, useMemo } from "react";

type TRouteParams = Readonly<Record<string, string | undefined>>;

type TRoutePolicy = {
  params: TRouteParams;
  normalizePath: (path: string) => string;
};

const RoutePolicyContext = createContext<TRoutePolicy>({
  params: {},
  normalizePath: (path) => path,
});

export const normalizeDefaultWorkspacePath = (path: string, workspaceSlug?: string): string => {
  if (!workspaceSlug || !path.startsWith("/")) return path;

  const [pathname, suffix = ""] = path.split(/(?=[?#])/u, 2);
  const escapedSlug = workspaceSlug.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&");
  const match = pathname.match(new RegExp(`^/${escapedSlug}/browse/([^/]+)/?$`, "u"));
  return match ? `/i/${match[1]}${suffix}` : path;
};

type TRoutePolicyProviderProps = {
  children: ReactNode;
  params: TRouteParams;
  defaultWorkspaceSlug?: string;
};

export function RoutePolicyProvider({ children, params, defaultWorkspaceSlug }: TRoutePolicyProviderProps) {
  const value = useMemo<TRoutePolicy>(() => {
    const effectiveParams =
      params.workItem && !params.workspaceSlug && defaultWorkspaceSlug
        ? { ...params, workspaceSlug: defaultWorkspaceSlug }
        : params;

    return {
      params: effectiveParams,
      normalizePath: (path) => normalizeDefaultWorkspacePath(path, defaultWorkspaceSlug),
    };
  }, [defaultWorkspaceSlug, params]);

  return <RoutePolicyContext.Provider value={value}>{children}</RoutePolicyContext.Provider>;
}

export const useRoutePolicy = () => useContext(RoutePolicyContext);
