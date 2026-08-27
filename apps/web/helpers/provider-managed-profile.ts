/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { IInstanceConfig, IUser } from "@plane/types";

/**
 * Whether the identity provider owns this account's name and picture.
 *
 * True when attribute sync is enabled for the provider the account signs in
 * through. The provider then rewrites the name, display name and avatar on every
 * sign-in, so an edit made here survives until the next login and no further —
 * and the avatar is worse than that, because sync deletes an uploaded file
 * outright rather than replacing it.
 *
 * This is deliberately not the same question as whether the account is
 * federated. An account can sign in through a provider with sync switched off,
 * and then these fields really are its own to edit.
 */
export const isProfileManagedByProvider = (
  config: IInstanceConfig | undefined,
  user: Pick<IUser, "last_login_medium"> | undefined | null
): boolean => (config?.provider_managed_profiles ?? []).includes(user?.last_login_medium ?? "");
