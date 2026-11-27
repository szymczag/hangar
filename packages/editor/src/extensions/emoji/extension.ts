/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// local imports
import { EmojiExtensionConfig } from "./extension-config";
import { emojiSuggestion } from "./suggestion";

export const EmojiExtension = EmojiExtensionConfig.configure({
  suggestion: emojiSuggestion,
});
