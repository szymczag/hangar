/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { ReactNode } from "react";
import { useEffect, useMemo, useRef } from "react";
import { observer } from "mobx-react";
import { useTheme } from "next-themes";
import { useLocation, useNavigate, useParams } from "react-router";
// helpers
import { applyCustomTheme, clearCustomTheme } from "@plane/utils";
import { RoutePolicyProvider, normalizeDefaultWorkspacePath } from "@/app/compat/next/route-policy-context";
// hooks
import { useAppTheme } from "@/hooks/store/use-app-theme";
import { useInstance } from "@/hooks/store/use-instance";
import { useRouterParams } from "@/hooks/store/use-router-params";
import { useWorkspace } from "@/hooks/store/use-workspace";
import { useUserProfile } from "@/hooks/store/user";

type TStoreWrapper = {
  children: ReactNode;
};

function StoreWrapper(props: TStoreWrapper) {
  const { children } = props;
  // theme
  const { setTheme } = useTheme();
  // router
  const params = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  // store hooks
  const { setQuery } = useRouterParams();
  const { config } = useInstance();
  const { getWorkspaceById } = useWorkspace();
  const { sidebarCollapsed, toggleSidebar } = useAppTheme();
  const { data: userProfile } = useUserProfile();
  // Track if we've initialized theme from server (one-time only)
  const hasInitializedThemeRef = useRef(false);
  // Track current user to reset on logout/login
  const currentUserIdRef = useRef<string | undefined>(undefined);
  // Track previous theme to detect transitions from custom theme
  const previousThemeRef = useRef<string | undefined>(undefined);
  const defaultWorkspaceSlug = config?.default_workspace_id
    ? getWorkspaceById(config.default_workspace_id)?.slug
    : undefined;
  const effectiveParams = useMemo(
    () =>
      params.workItem && !params.workspaceSlug && defaultWorkspaceSlug
        ? { ...params, workspaceSlug: defaultWorkspaceSlug }
        : params,
    [defaultWorkspaceSlug, params]
  );

  /**
   * Sidebar collapsed fetching from local storage
   */
  useEffect(() => {
    const localValue = localStorage && localStorage.getItem("app_sidebar_collapsed");
    const localBoolValue = localValue === "true";
    if (localValue && sidebarCollapsed === undefined) toggleSidebar(localBoolValue);
  }, [sidebarCollapsed, setTheme, toggleSidebar]);

  /**
   * Effect 1: Initial theme sync from server (one-time only)
   *
   * This effect runs ONCE per user session to load theme from server.
   * After initial load, all theme changes are localStorage-driven (next-themes).
   * This prevents a feedback loop where server updates trigger UI updates in a cycle.
   */
  useEffect(() => {
    const userId = userProfile?.id;

    // Reset initialization flag when user changes (logout/login)
    // This handles both logout (userId becomes undefined) and login (userId changes)
    if (userId !== currentUserIdRef.current) {
      hasInitializedThemeRef.current = false;
      previousThemeRef.current = undefined;
      currentUserIdRef.current = userId;
    }

    // Only initialize theme from server on FIRST load for this user
    if (!userProfile?.theme?.theme || hasInitializedThemeRef.current) {
      return; // Skip if already initialized or no profile data
    }

    // Apply theme from server profile (one-time only)
    setTheme(userProfile?.theme?.theme || "system");

    // Mark as initialized - prevents future syncs from server
    hasInitializedThemeRef.current = true;
  }, [userProfile?.id, userProfile?.theme?.theme, setTheme]);

  /**
   * Effect 2: Custom theme CSS application (runs on every change)
   *
   * This effect applies or clears custom theme CSS variables whenever
   * the theme changes. It runs independently of the initial sync effect.
   */
  useEffect(() => {
    if (!userProfile?.theme?.theme) return;

    const currentTheme = userProfile?.theme?.theme;
    const previousTheme = previousThemeRef.current;
    const themeData = userProfile?.theme;

    // Apply custom theme if current theme is custom
    if (currentTheme === "custom" && themeData.primary && themeData.background && themeData.darkPalette !== undefined) {
      applyCustomTheme(themeData.primary, themeData.background, themeData.darkPalette ? "dark" : "light");
    }
    // Clear custom theme CSS when switching away from custom
    else if (previousTheme === "custom" && currentTheme !== "custom") {
      clearCustomTheme();
      // No reload needed - let CSS cascade handle it naturally
    }

    // Update previous theme for next comparison
    previousThemeRef.current = currentTheme;
  }, [userProfile?.theme]);

  useEffect(() => {
    setQuery(effectiveParams);
  }, [effectiveParams, setQuery]);

  useEffect(() => {
    const currentPath = `${location.pathname}${location.search}${location.hash}`;
    const normalizedPath = normalizeDefaultWorkspacePath(currentPath, defaultWorkspaceSlug);
    if (normalizedPath !== currentPath) navigate(normalizedPath, { replace: true });
  }, [defaultWorkspaceSlug, location.hash, location.pathname, location.search, navigate]);

  return (
    <RoutePolicyProvider params={params} defaultWorkspaceSlug={defaultWorkspaceSlug}>
      {children}
    </RoutePolicyProvider>
  );
}

export default observer(StoreWrapper);
