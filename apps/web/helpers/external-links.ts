/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { IInstanceConfig } from "@plane/types";

/**
 * Whether the application may point anyone at a host this instance does not run.
 *
 * Off unless an operator turns it on. Hangar is deployed inside organisations,
 * where a link to a code-hosting site is a link out of the building for someone
 * who did not ask to leave it — and every such link tells the far end who is
 * looking, and from where.
 *
 * The AGPL source offer is **not** governed by this and is never hidden: section
 * 13 requires it of anyone running a modified version over a network. An operator
 * who wants that inside the building too points `HANGAR_SOURCE_URL` at their own
 * mirror, which is where the link already reads from.
 */
export const showExternalLinks = (config: IInstanceConfig | undefined): boolean => config?.show_external_links === true;
