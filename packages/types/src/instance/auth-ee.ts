/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Fork (see FORK.md): upstream ships both types as `never`; this file is the
// designated hook for extended authentication modes.

export type TExtendedLoginMediums = "oidc" | "saml";

export type TExtendedInstanceAuthenticationModeKeys = "oidc" | "saml";
