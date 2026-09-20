/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { pathToFileURL } from "node:url";

import { RUNTIME_STYLE_ELEMENTS } from "../src/index.mjs";

test("the Base UI scrollbar style matches the installed library", async () => {
  // Base UI inserts this <style> itself; the policy allows it by the hash of
  // this exact text. If an upgrade changes the text, the hash stops matching
  // and the style is refused, so the difference has to surface here.
  // Resolved from @plane/propel, the package that depends on Base UI, by its
  // path in the repository: a package dependency on it would close a build
  // cycle (propel depends on utils, which depends on this package).
  const propelRequire = createRequire(new URL("../../propel/package.json", import.meta.url));
  const root = dirname(propelRequire.resolve("@base-ui-components/react/package.json"));
  const { styleDisableScrollbar } = await import(pathToFileURL(join(root, "esm/utils/styles.js")).href);
  assert.ok(RUNTIME_STYLE_ELEMENTS.includes(styleDisableScrollbar.element.props.children));
});
