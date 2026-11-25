// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

/**
 * The web entry hydrates only after i18n is ready (upstream makeplane/plane
 * 1a76f29c79, as the published boards do), and everything React must not
 * render without is set up before that wait: the Trusted Types policies and
 * the emoji data URL of both pickers, so neither falls back to a CDN (the
 * 1.4 picker is only rendered by the editor's callout logo picker now).
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const entry = readFileSync(new URL("../app/entry.client.tsx", import.meta.url), "utf8");
const provider = readFileSync(new URL("../app/provider.tsx", import.meta.url), "utf8");

const indexOf = (pattern) => {
  const match = pattern.exec(entry);
  assert.ok(match, `entry.client.tsx has no ${pattern}`);
  return match.index;
};

test("web hydrates after initPromise, with policies and emoji data set first", () => {
  assert.match(entry, /import \{ initPromise \} from "@plane\/i18n";/);
  const policies = indexOf(/^installTrustedTypesPolicies\(/m);
  const propelEmoji = indexOf(/^setEmojiDataUrl\(emojiDataUrl\);/m);
  const blocksEmoji = indexOf(/^setBlocksEmojiDataUrl\(emojiDataUrl\);/m);
  const wait = indexOf(/^void initPromise\.catch\(\(\) => \{\}\)\.then\(hydrate\);/m);
  const hydrate = indexOf(/hydrateRoot\(/);
  assert.ok(policies < wait && propelEmoji < wait && blocksEmoji < wait);
  // hydrateRoot is only reached through the `hydrate` callback.
  assert.ok(indexOf(/^const hydrate = \(\) =>/m) < hydrate);
  assert.equal(entry.match(/hydrateRoot\(/g).length, 1);
});

test("both emoji pickers read the data this app serves", () => {
  assert.match(
    entry,
    /import \{ setEmojiDataUrl as setBlocksEmojiDataUrl \} from "@plane\/blocks\/emoji-icon-picker";/
  );
  assert.match(entry, /import \{ setEmojiDataUrl \} from "@plane\/propel\/emoji-icon-picker";/);
  assert.match(entry, /const emojiDataUrl = `\$\{import\.meta\.env\.BASE_URL\}emojibase`;/);
});

test("the toast viewport is mounted inside TranslationProvider, and only the blocks one", () => {
  // Phase 9 moved the last `setToast` callers in web off @plane/propel/toast,
  // so its <Toast> viewport is gone: a toast raised through it would now show
  // nowhere, which the legacy-imports contract keeps from happening.
  const translation = provider.indexOf("<TranslationProvider>");
  const blocks = provider.indexOf("<PlaneToastProvider>");
  const end = provider.indexOf("</TranslationProvider>");
  assert.ok(translation >= 0 && blocks > translation);
  assert.ok(provider.indexOf("</PlaneToastProvider>") < end);
  assert.match(provider, /import \{ PlaneToastProvider \} from "@plane\/blocks\/toast";/);
  assert.doesNotMatch(provider, /<Toast\b|@plane\/propel\/toast/);
});
