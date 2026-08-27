/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Fork (see FORK.md): upstream ships this hook as an empty list. mergeRoutes
// deep-merges by layout file path, so replicating the core layout chain nests
// these routes inside the existing project-detail layout without core edits.

import { layout, route } from "@react-router/dev/routes";
import type { RouteConfigEntry } from "@react-router/dev/routes";

export const extendedRoutes: RouteConfigEntry[] = [
  layout("./(all)/layout.tsx", [
    layout("./(all)/[workspaceSlug]/layout.tsx", [
      layout("./(all)/[workspaceSlug]/(projects)/layout.tsx", [
        layout("./(all)/[workspaceSlug]/(projects)/browse/[workItem]/layout.tsx", [
          route("i/:workItem", "./(all)/short-work-item/page.tsx"),
        ]),
      ]),
    ]),
    layout("./(all)/[workspaceSlug]/layout.tsx", [
      layout("./(all)/[workspaceSlug]/(projects)/layout.tsx", [
        layout("./(all)/[workspaceSlug]/(projects)/projects/(detail)/[projectId]/layout.tsx", [
          route(
            ":workspaceSlug/projects/:projectId/epics",
            "./(all)/[workspaceSlug]/(projects)/projects/(detail)/[projectId]/epics/(list)/page.tsx"
          ),
        ]),
      ]),
      layout("./(all)/[workspaceSlug]/(settings)/layout.tsx", [
        layout("./(all)/[workspaceSlug]/(settings)/settings/projects/layout.tsx", [
          layout("./(all)/[workspaceSlug]/(settings)/settings/projects/[projectId]/layout.tsx", [
            // Work item types settings
            route(
              ":workspaceSlug/settings/projects/:projectId/work-item-types",
              "./(all)/[workspaceSlug]/(settings)/settings/projects/[projectId]/work-item-types/page.tsx"
            ),
          ]),
        ]),
      ]),
    ]),
  ]),
];
