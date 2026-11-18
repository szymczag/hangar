/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { EmojiItem } from "./emoji";

// Hangar removes fallback images from its configured emoji set, so native
// Unicode availability is the complete rendering contract for this extension.
export const hasRenderableEmoji = (emojiItem: EmojiItem): boolean => Boolean(emojiItem.emoji);
