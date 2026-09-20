/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { Plugin } from "vite";

/** Where the files are served and emitted, under the app's base path. */
export declare const EMOJI_DATA_PATH: string;

/** Serves and emits the emoji picker's data from the app itself. */
export declare function emojiData(): Plugin;
