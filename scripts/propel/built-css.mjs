// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

/**
 * Shared by the built-asset tests of the apps on Propel (apps/admin/tests and
 * apps/space/tests): the class tokens of every vendored Propel variants file,
 * and the built stylesheet of an app to look them up in. Tailwind drops a class
 * it does not know without a warning, so a utility the catalog's Tailwind does
 * not have only shows as a broken screen.
 */

import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync } from "node:fs";

const ROOT = new URL("../../", import.meta.url);
const ELEMENTS = new URL("packages/makeplane-propel/src/elements/", ROOT);

/** `apps/<app>/build/client/<path>`, asserting the app was built. */
export function builtFile(app, path) {
  const url = new URL(`apps/${app}/build/client/${path}`, ROOT);
  assert.ok(existsSync(url), `apps/${app}/build/client/${path} is missing: build ${app} first`);
  return readFileSync(url, "utf8");
}

/** Every stylesheet of the app's client build, concatenated. */
export function builtCss(app) {
  const assets = readdirSync(new URL(`apps/${app}/build/client/assets/`, ROOT)).filter((file) => file.endsWith(".css"));
  assert.ok(assets.length > 0, `the ${app} build has no stylesheet`);
  return assets.map((file) => builtFile(app, `assets/${file}`)).join("\n");
}

// CSS.escape (CSSOM), which is how Tailwind writes a class into its selector.
export function cssEscape(value) {
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

/** `{ element, url }` for every `packages/makeplane-propel/src/elements/<element>/variants.ts`. */
export const variantFiles = readdirSync(ELEMENTS)
  .map((element) => ({ element, url: new URL(`${element}/variants.ts`, ELEMENTS) }))
  .filter(({ url }) => existsSync(url));

/** `element: token` for every variant class the app's built CSS has no rule for. */
export function missingVariantClasses(app) {
  const css = builtCss(app);
  const missing = [];
  for (const { element, url } of variantFiles) {
    for (const token of classTokens(readFileSync(url, "utf8"))) {
      if (!css.includes(`.${cssEscape(token)}`)) missing.push(`${element}: ${token}`);
    }
  }
  return missing;
}
