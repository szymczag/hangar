/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { gitHubEmojis } from "@tiptap/extension-emoji";
// local imports
import type { EmojiItem } from "./emoji";

/**
 * The emoji set the editor offers and stores by name: GitHub's list, without
 * the entries that have no Unicode character and without `fallbackImage`, so
 * nothing ever loads an emoji image from a CDN. It is bundled data; reading it
 * fetches nothing.
 */
export const EDITOR_EMOJIS: EmojiItem[] = gitHubEmojis
  .filter((item) => item.emoji)
  .map(({ fallbackImage: _fallbackImage, ...emoji }) => emoji);
