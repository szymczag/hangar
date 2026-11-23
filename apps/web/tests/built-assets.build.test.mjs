// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

/**
 * Checks on the built web app, run after `react-router build` (CI runs them
 * after the Trusted Types bundle check). Web loads the Propel entry point
 * (packages/tailwind-config/propel.css) while its components move to Propel in
 * phases, so the same failures God Mode and the published boards guard
 * against apply here, and they only show in a browser:
 *
 * - Propel's variants use utilities that need Tailwind 4.2 (`inset-e-4`, ...).
 *   Tailwind drops a class it does not know without a warning.
 * - propel.css has no floating-overlay layer, which index.css had. Web's own
 *   stylesheet carries it; without it Popper menus open behind peek views and
 *   modals.
 * - The SPA prerender of index.html keeps its HydrateFallback loader, which
 *   the first client render (after entry.client.tsx waits for i18n) adopts.
 *
 *   pnpm turbo run build --filter=web && pnpm test:web-build
 */

import assert from "node:assert/strict";
import test from "node:test";

import { builtCss, builtFile, missingVariantClasses } from "../../../scripts/propel/built-css.mjs";

test("every utility in the Propel variants has a rule in the built web CSS", () => {
  assert.deepEqual(
    missingVariantClasses("web"),
    [],
    "Tailwind generated no rule for these classes; is the catalog too old?"
  );
});

test("the toast's logical insets are in the built web CSS", () => {
  const css = builtCss("web");
  for (const utility of ["inset-e-4", "inset-e-0", "inset-s-0", "inset-e-2"]) {
    assert.match(css, new RegExp(`\\.${utility}\\{inset-inline-(end|start):`), utility);
  }
});

test("the built web CSS has the Propel tokens, not index.css's", () => {
  const css = builtCss("web");
  // Propel names its keyframes in kebab case; index.css's camelCase ones are gone.
  assert.match(css, /@keyframes slide-in-from-bottom\{/);
  assert.doesNotMatch(css, /@keyframes slideInFromBottom\{/);
});

test("Popper content sits on the floating-overlay layer in the built web CSS", () => {
  const css = builtCss("web");
  assert.match(css, /--z-index-floating-overlay:110[;}]/);
  assert.match(css, /\[data-popper-placement\]\{z-index:var\(--z-index-floating-overlay\)!important\}/);
});

test("the prerendered index.html carries the HydrateFallback loader", () => {
  const html = builtFile("web", "index.html");
  const body = html.slice(html.indexOf("<body"), html.indexOf("window.__reactRouterContext"));
  assert.match(body, /<img src="[^"]*\/assets\/logo-loader-[^"]+\.png" alt="Hangar"/);
});
