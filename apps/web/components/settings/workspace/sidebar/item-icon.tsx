/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { IconGlyph } from "@makeplane/propel/components/icon";
import {
  BuildingOutline,
  ExportOutline,
  HomeOutline,
  ImportsOutline,
  InfoOutline,
  MembersOutline,
  TemplatesOutline,
  WebhooksOutline,
} from "@makeplane/propel/icons";
// plane imports
import type { ISvgIcons } from "@plane/blocks/icons";
import type { TWorkspaceSettingsTabs } from "@plane/types";

export const WORKSPACE_SETTINGS_ICONS: Record<TWorkspaceSettingsTabs, IconGlyph | React.FC<ISvgIcons>> = {
  general: BuildingOutline,
  members: MembersOutline,
  export: ExportOutline,
  // Fork (see FORK.md): the Hangar project page, not billing
  "billing-and-plans": InfoOutline,
  webhooks: WebhooksOutline,
  // Fork (see FORK.md)
  imports: ImportsOutline,
  "home-defaults": HomeOutline,
  "workshop-templates": TemplatesOutline,
};
