// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

/**
 * The web entry hydrates only after i18n is ready (upstream makeplane/plane
 * 1a76f29c79, as the published boards do), and everything React must not
 * render without is set up before that wait: the Trusted Types policies and
 * the emoji data URL of the `@plane/blocks` picker, so it never falls back to
 * a CDN. Since phase 9b that is the only picker web renders: the editor's
 * callout logo picker is the same one.
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
  const emoji = indexOf(/^setEmojiDataUrl\(`\$\{import\.meta\.env\.BASE_URL\}emojibase`\);/m);
  const wait = indexOf(/^void initPromise\.catch\(\(\) => \{\}\)\.then\(hydrate\);/m);
  const hydrate = indexOf(/hydrateRoot\(/);
  // The policies first, so even the picker's data fetch runs under them.
  assert.ok(policies < emoji && emoji < wait);
  // hydrateRoot is only reached through the `hydrate` callback.
  assert.ok(indexOf(/^const hydrate = \(\) =>/m) < hydrate);
  assert.equal(entry.match(/hydrateRoot\(/g).length, 1);
});

test("the emoji picker reads the data this app serves, and only the blocks picker is configured", () => {
  assert.match(entry, /import \{ setEmojiDataUrl \} from "@plane\/blocks\/emoji-icon-picker";/);
  assert.equal(entry.match(/setEmojiDataUrl\(/g).length, 1);
  assert.doesNotMatch(entry, /@plane\/propel\/emoji-icon-picker/);
});

test("the editor's callout picker is the blocks picker that call configures", () => {
  const selector = readFileSync(
    new URL("../../../packages/editor/src/extensions/callout/logo-selector.tsx", import.meta.url),
    "utf8"
  );
  assert.match(selector, /from "@plane\/blocks\/emoji-icon-picker";/);
  assert.doesNotMatch(selector, /@plane\/propel\/emoji-icon-picker/);
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
