/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { index, layout, route } from "@react-router/dev/routes";
import type { RouteConfig } from "@react-router/dev/routes";

export default [
  layout("./(all)/(home)/layout.tsx", [
    index("./(all)/(home)/page.tsx"),
    // Fork (see FORK.md): second factor for the console. Inside the home
    // layout because the caller is not authenticated yet.
    route("2fa", "./(all)/(home)/2fa/page.tsx"),
    route("2fa/enroll", "./(all)/(home)/2fa/enroll/page.tsx"),
  ]),
  layout("./(all)/(dashboard)/layout.tsx", [
    route("general", "./(all)/(dashboard)/general/page.tsx"),
    route("workspace", "./(all)/(dashboard)/workspace/page.tsx"),
    // Fork (see FORK.md)
    route("users", "./(all)/(dashboard)/users/page.tsx"),
    route("workspace/create", "./(all)/(dashboard)/workspace/create/page.tsx"),
    route("email", "./(all)/(dashboard)/email/page.tsx"),
    route("authentication", "./(all)/(dashboard)/authentication/page.tsx"),
    route("authentication/github", "./(all)/(dashboard)/authentication/github/page.tsx"),
    route("authentication/gitlab", "./(all)/(dashboard)/authentication/gitlab/page.tsx"),
    route("authentication/google", "./(all)/(dashboard)/authentication/google/page.tsx"),
    route("authentication/gitea", "./(all)/(dashboard)/authentication/gitea/page.tsx"),
    // Fork (see FORK.md)
    route("authentication/oidc", "./(all)/(dashboard)/authentication/oidc/page.tsx"),
    route("authentication/saml", "./(all)/(dashboard)/authentication/saml/page.tsx"),
    route("authentication/domains", "./(all)/(dashboard)/authentication/domains/page.tsx"),
    route("authentication/identity-import", "./(all)/(dashboard)/authentication/identity-import/page.tsx"),
    route("ai", "./(all)/(dashboard)/ai/page.tsx"),
    route("image", "./(all)/(dashboard)/image/page.tsx"),
  ]),
  // Catch-all route for 404 handling - must be last
  route("*", "./components/404.tsx"),
] satisfies RouteConfig;
