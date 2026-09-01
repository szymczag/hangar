// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

// The operator favicon is applied to a document whose icon links were written
// by `links()` in root.tsx, before any instance configuration existed. These
// pin the parts of that swap that are easy to get subtly wrong.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const repoRoot = fileURLToPath(new URL("../../../", import.meta.url));
const read = (relativePath) => readFileSync(path.join(repoRoot, relativePath), "utf8");

const helper = read("apps/web/helpers/instance-favicon.ts");
const wrapper = read("apps/web/core/lib/wrappers/instance-wrapper.tsx");

test("the built-in icon is detached rather than merely overridden", () => {
  // Several browsers prefer `shortcut icon` or the first icon they parsed, so
  // appending a second <link> is not reliably an override.
  assert.match(helper, /\.remove\(\)/, "built-in icon links must be detached");
  assert.match(helper, /insertBefore/, "and put back when the operator clears the icon");
});

test("clearing the favicon restores the built-in one", () => {
  assert.match(
    helper,
    /if \(!url\)[\s\S]{0,200}restoreBuiltIn\(\)/,
    "an empty favicon_url must restore what root.tsx declared"
  );
});

test("the icon is applied in an effect, not during render", () => {
  // It mutates document.head; doing that while rendering is a side effect in
  // the render phase and misbehaves under StrictMode double-invocation.
  assert.match(
    wrapper,
    /useEffect\(\(\) => \{\s*applyInstanceFavicon\(config\?\.favicon_url\);\s*\}, \[config\?\.favicon_url\]\)/,
    "applyInstanceFavicon must run in a useEffect keyed on the config value"
  );
});

test("the helper is safe to import where there is no document", () => {
  assert.match(helper, /typeof document === "undefined"/, "server rendering must not touch the DOM");
});
