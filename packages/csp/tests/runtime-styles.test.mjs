/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
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

// Base UI 1.x (@base-ui/react) is a separate package from the beta (@base-ui-components/react):
// @makeplane/propel and @plane/blocks use it, and the workspace pins one copy for both.
const baseUiRoot = () => {
  const makeplanePropelRequire = createRequire(new URL("../../makeplane-propel/package.json", import.meta.url));
  return dirname(makeplanePropelRequire.resolve("@base-ui/react/package.json"));
};

test("the Base UI 1.x scrollbar style matches the installed library", async () => {
  // Same <style> as the beta, now built per call with the CSPProvider nonce.
  const { styleDisableScrollbar } = await import(pathToFileURL(join(baseUiRoot(), "utils/styles.mjs")).href);
  const element = styleDisableScrollbar.getElement(undefined);
  assert.equal(element.type, "style");
  assert.ok(RUNTIME_STYLE_ELEMENTS.includes(element.props.children));
});

test("Base UI 1.x renders no other inline <style> or <script> element", () => {
  // The policy has no nonce and no 'unsafe-inline', so every element Base UI renders
  // with inline content needs review. Today there are two: the scrollbar <style>
  // above, and PrehydrationScript, which renders only while React hydrates
  // server-rendered markup and whose body is an empty stub under the bundlers'
  // "browser" condition. Admin and web are client-only builds; space is
  // server-rendered but does not use Base UI 1.x. A space that does would need
  // the per-request nonce passed through Base UI's CSPProvider.
  const root = baseUiRoot();
  const found = [];
  const walk = (dir) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const path = join(dir, entry.name);
      if (entry.isDirectory()) walk(path);
      else if (entry.name.endsWith(".mjs") && /_jsx[s]?\(\s*"(style|script)"/.test(readFileSync(path, "utf8"))) {
        found.push(relative(root, path));
      }
    }
  };
  walk(root);
  assert.deepEqual(found.toSorted(), ["internals/PrehydrationScript.mjs", "utils/styles.mjs"]);

  const stub = readFileSync(join(root, "internals/prehydrationScript.stub.mjs"), "utf8");
  assert.match(stub, /export const script = '';/);
});
