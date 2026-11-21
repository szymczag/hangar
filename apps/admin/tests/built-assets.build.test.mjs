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
import { existsSync, readdirSync, readFileSync } from "node:fs";
import test from "node:test";

const ROOT = new URL("../../../", import.meta.url);
const BUILD = new URL("apps/admin/build/client/", ROOT);
const ELEMENTS = new URL("packages/makeplane-propel/src/elements/", ROOT);

function builtFile(path) {
  const url = new URL(path, BUILD);
  assert.ok(existsSync(url), `apps/admin/build/client/${path} is missing: build admin first`);
  return readFileSync(url, "utf8");
}

function builtCss() {
  const assets = readdirSync(new URL("assets/", BUILD)).filter((file) => file.endsWith(".css"));
  assert.ok(assets.length > 0, "the admin build has no stylesheet");
  return assets.map((file) => builtFile(`assets/${file}`)).join("\n");
}

// CSS.escape (CSSOM), which is how Tailwind writes a class into its selector.
function cssEscape(value) {
  let out = "";
  for (const [index, char] of [...value].entries()) {
    const code = char.codePointAt(0);
    if (index === 0 && code >= 0x30 && code <= 0x39) out += `\\3${char} `;
    else if (code >= 0x80 || /[\w-]/.test(char)) out += char;
    else out += `\\${char}`;
  }
  return out;
}

// String literals in a variants file that are not classes: variant names used
// as values, group markers that only name an ancestor, and custom properties.
const NOT_A_CLASS = new Set(["danger-outline", "group/list-item"]);

function classTokens(source) {
  const code = source
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:"'`])\/\/.*$/gm, "$1")
    .replace(/\bfrom\s+(["'])[^"']*\1/g, "");
  const literals = [...code.matchAll(/"((?:[^"\\\n]|\\.)*)"|'((?:[^'\\\n]|\\.)*)'|`([^`]*)`/g)].map(
    ([, double, single, template]) => double ?? single ?? template
  );
  return [...new Set(literals.flatMap((literal) => literal.split(/\s+/)))].filter(
    (token) => /[-:[]/.test(token) && !token.startsWith("--") && !token.includes("${") && !NOT_A_CLASS.has(token)
  );
}

const variantFiles = readdirSync(ELEMENTS)
  .map((element) => ({ element, url: new URL(`${element}/variants.ts`, ELEMENTS) }))
  .filter(({ url }) => existsSync(url));

test("the Propel elements God Mode relies on have variants files", () => {
  const elements = new Set(variantFiles.map(({ element }) => element));
  for (const element of ["toast", "dialog", "select", "switch", "input", "banner", "menu"]) {
    assert.ok(elements.has(element), `${element}/variants.ts is missing`);
  }
});

test("every utility in the Propel variants has a rule in the built admin CSS", () => {
  const css = builtCss();
  const missing = [];
  for (const { element, url } of variantFiles) {
    for (const token of classTokens(readFileSync(url, "utf8"))) {
      if (!css.includes(`.${cssEscape(token)}`)) missing.push(`${element}: ${token}`);
    }
  }
  assert.deepEqual(missing, [], "Tailwind generated no rule for these classes; is the catalog too old?");
});

test("the toast's logical insets are in the built admin CSS", () => {
  const css = builtCss();
  for (const utility of ["inset-e-4", "inset-e-0", "inset-s-0", "inset-e-2"]) {
    assert.match(css, new RegExp(`\\.${utility}\\{inset-inline-(end|start):`), utility);
  }
});

test("the prerendered index.html carries the HydrateFallback loader", () => {
  const html = builtFile("index.html");
  const body = html.slice(html.indexOf("<body"), html.indexOf("window.__reactRouterContext"));
  assert.match(body, /<img src="[^"]*\/assets\/logo-loader-[^"]+\.png" alt="Hangar"/);
});
