/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Fork (see FORK.md): labels for the extended sign-in mediums.

import type { TExtendedLoginMediums } from "@plane/types";

export const EXTENDED_LOGIN_MEDIUM_LABELS: Record<TExtendedLoginMediums, string> = {
  oidc: "OIDC",
  saml: "SAML",
};
