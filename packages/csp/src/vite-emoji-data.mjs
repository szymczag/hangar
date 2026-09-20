// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only
// See the LICENSE file for details.

/**
 * Serve the emoji picker's data from this instance.
 *
 * frimousse fetches `${emojibaseUrl}/${locale}/${file}.json`, and its default
 * base is a public CDN: every open of the picker would tell a third party who
 * is using this deployment. The files come from the `emojibase-data` package
 * instead, emitted into the build at a fixed path and served from node_modules
 * during development, so the browser only ever talks to the page's own origin
 * (docs/content-security-policy.md).
 *
 * The version is the one in the lockfile, so it updates with every other
 * dependency rather than silently, whenever the CDN's "latest" moved.
 */

import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import path from "node:path";

/** Where the files are served and emitted, under the app's base path. */
export const EMOJI_DATA_PATH = "emojibase";

/** Only what the picker asks for: English, and only those two files. */
const FILES = ["en/data.json", "en/messages.json"];

const source = (require_, file) => readFileSync(require_.resolve(`emojibase-data/${file}`), "utf8");

export function emojiData() {
  const require_ = createRequire(import.meta.url);
  return {
    name: "hangar-emoji-data",
    configureServer(server) {
      server.middlewares.use((request, response, next) => {
        const file = FILES.find((name) => request.url?.endsWith(`/${EMOJI_DATA_PATH}/${name}`));
        if (!file) return next();
        response.setHeader("Content-Type", "application/json");
        response.end(source(require_, file));
      });
    },
    generateBundle() {
      for (const file of FILES) {
        this.emitFile({
          type: "asset",
          fileName: path.posix.join(EMOJI_DATA_PATH, file),
          source: source(require_, file),
        });
      }
    },
  };
}
