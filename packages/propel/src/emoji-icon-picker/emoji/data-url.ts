/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Where the emoji picker reads its data from.
//
// frimousse's default is a public CDN, which would tell a third party who is
// using this deployment every time the picker opens, and which the
// Content-Security-Policy's connect-src does not allow. The data is served
// from this instance instead (scripts/vite-emoji-data.mjs). An app whose base
// path is not "/" -- the published boards, the console -- sets its own at
// start-up, because the path has to resolve under it.

let dataUrl = "/emojibase";

/** Call once, before the first picker renders, with an absolute same-origin path. */
export const setEmojiDataUrl = (url: string): void => {
  dataUrl = url;
};

export const getEmojiDataUrl = (): string => dataUrl;
