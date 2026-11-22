// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

/**
 * Checks on the built God Mode, run after `react-router build` (CI runs them
 * after the Trusted Types bundle check). Both failures they guard against
 * passed every source-level check and only showed in a browser:
 *
 * - Propel's variants use utilities that need a newer Tailwind than the
 *   catalog had (`inset-e-4`, `inset-s-0`, ... arrived in 4.2). Tailwind drops
 *   a class it does not know without a warning, so the toasts landed in the
 *   bottom-left corner with their close button over the icon.
 * - The SPA prerender of index.html lost its HydrateFallback loader when a
 *   provider above it rendered nothing until i18n was ready, and every cached
 *   load then hydrated into a body that did not match (React #418).
 *
 *   pnpm turbo run build --filter=admin && pnpm test:admin-build
 */

import assert from "node:assert/strict";
import test from "node:test";

import { builtCss, builtFile, missingVariantClasses, variantFiles } from "../../../scripts/propel/built-css.mjs";

test("the Propel elements God Mode relies on have variants files", () => {
  const elements = new Set(variantFiles.map(({ element }) => element));
  for (const element of ["toast", "dialog", "select", "switch", "input", "banner", "menu"]) {
    assert.ok(elements.has(element), `${element}/variants.ts is missing`);
  }
});

test("every utility in the Propel variants has a rule in the built admin CSS", () => {
  assert.deepEqual(
    missingVariantClasses("admin"),
    [],
    "Tailwind generated no rule for these classes; is the catalog too old?"
  );
});

test("the toast's logical insets are in the built admin CSS", () => {
  const css = builtCss("admin");
  for (const utility of ["inset-e-4", "inset-e-0", "inset-s-0", "inset-e-2"]) {
    assert.match(css, new RegExp(`\\.${utility}\\{inset-inline-(end|start):`), utility);
  }
});

test("the prerendered index.html carries the HydrateFallback loader", () => {
  const html = builtFile("admin", "index.html");
  const body = html.slice(html.indexOf("<body"), html.indexOf("window.__reactRouterContext"));
  assert.match(body, /<img src="[^"]*\/assets\/logo-loader-[^"]+\.png" alt="Hangar"/);
});
