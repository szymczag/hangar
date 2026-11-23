/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Outlet } from "react-router";
// plane imports
import { cn } from "@plane/utils";
// Hangar extension
import { MaintenanceBar } from "@/plane-web/components/instance/maintenance-bar";
// local
import { AppProvider } from "./provider";

// Pathless layout route wrapping every route (see app/routes.ts). Providers, the store
// layer, and app chrome live here instead of root.tsx so they stay out of the SPA-mode
// server build — see the note in app/root.tsx. The trailing-slash middleware upstream
// declares here stays on the root route in Hangar (see app/root.tsx).
export default function AppShellLayout() {
  return (
    <AppProvider>
      <div className={cn("relative flex h-screen w-full flex-col overflow-hidden bg-canvas", "desktop-app-container")}>
        {/* Fork (see FORK.md): mounted here rather than inside InstanceWrapper,
            which early-returns its own view on an API error or an unfinished
            setup -- a bar below it would disappear exactly when things are
            going wrong. This is the only slot covering sign-in, onboarding and
            the error routes.

            `<main>` was `h-full`, which inside a `flex-col h-screen` pushes the
            app's bottom edge past the viewport as soon as it has a sibling, and
            `overflow-hidden` then clips it. `min-h-0 flex-1` is equivalent to
            `h-full` while the bar renders null, so with no notice the layout is
            unchanged; `min-h-0` is required or the nested scroll containers
            refuse to shrink below their content. */}
        <MaintenanceBar />
        <main className="relative min-h-0 w-full flex-1 overflow-hidden">
          <Outlet />
        </main>
      </div>
    </AppProvider>
  );
}
