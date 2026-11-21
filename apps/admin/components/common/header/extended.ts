/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Fork (see FORK.md): breadcrumb labels for the Hangar-only console pages, which
// would otherwise show their URL segment in capitals.
export const EXTENDED_HEADER_SEGMENT_LABELS: Record<string, string> = {
  users: "Users",
  branding: "Branding",
  maintenance: "Maintenance notice",
  oidc: "OIDC",
  saml: "SAML",
  domains: "Domain policy",
  "identity-import": "Identity import",
};
