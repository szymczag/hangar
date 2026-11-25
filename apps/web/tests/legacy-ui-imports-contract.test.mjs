// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

/**
 * Web moved to Propel (`@makeplane/propel`) and `@plane/blocks` in phases 0-9.
 * After phase 9a only the files below may still import the four legacy
 * packages: `@plane/ui`, the in-repo `@plane/propel`, Headless UI and lucide.
 * Phase 9b moves the first two and then drops the packages from web.
 *
 * - the maintenance bar sits above every page, so moving it moves nearly every
 *   baseline, and it gets a pass of its own;
 * - the edition badge is the build identity dialog's trigger, moved with it;
 * - the entry points the 1.4 emoji picker at this app's data, because the
 *   editor's callout logo picker (`packages/editor`) still renders it, and it
 *   must not fall back to a CDN (CSP).
 *
 * Anything else that imports them is a regression. A new `setToast` from
 * `@plane/propel/toast` is the sharpest case: its viewport is gone from the
 * provider, so that toast would show nowhere.
 */

import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

const SKIP = new Set(["node_modules", "build", "dist", ".react-router", ".turbo", "public", "tests"]);

function* sources(directory) {
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    if (SKIP.has(entry.name)) continue;
    const full = path.join(directory, entry.name);
    if (entry.isDirectory()) yield* sources(full);
    else if (/\.(tsx?|mjs|js)$/.test(entry.name) && !/\.config\.(ts|mjs|js)$/.test(entry.name)) yield full;
  }
}

// Comments do not import anything: upstream's export form keeps a commented-out
// lucide import, and that is no reason to list it.
const stripComments = (source) => source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:"'`\\])\/\/.*$/gm, "$1");

const LEGACY =
  /(?:from\s*|import\s*\(\s*|import\s+|vi\.mock\(\s*|require\(\s*)["'`]((?:@plane\/ui|@plane\/propel|@headlessui\/react|lucide-react)(?:\/[^"'`]*)?)["'`]/g;

/** Each file allowed to import a legacy package, with exactly what it may import. */
const ALLOWED = {
  "ce/components/instance/maintenance-bar.tsx": ["lucide-react", "@plane/propel/banner"],
  "components/workspace/edition-badge.tsx": ["@plane/propel/tooltip", "@plane/propel/button"],
  "app/entry.client.tsx": ["@plane/propel/emoji-icon-picker"],
};

const found = new Map();
for (const file of sources(root)) {
  const relative = path.relative(root, file).split(path.sep).join("/");
  const specifiers = [...stripComments(readFileSync(file, "utf8")).matchAll(LEGACY)].map((match) => match[1]);
  if (specifiers.length) found.set(relative, [...new Set(specifiers)].toSorted());
}

test("the scan reaches web's sources", () => {
  assert.ok([...sources(root)].length > 1500);
});

test("only the 9b allowlist imports @plane/ui, @plane/propel, Headless UI or lucide", () => {
  const unexpected = [...found.keys()].filter((file) => !(file in ALLOWED));
  assert.deepEqual(unexpected, [], `move these to @makeplane/propel or @plane/blocks: ${unexpected.join(", ")}`);
});

for (const [file, allowed] of Object.entries(ALLOWED)) {
  test(`${file} imports only what the allowlist names`, () => {
    for (const specifier of found.get(file) ?? []) {
      assert.ok(allowed.includes(specifier), `${file} newly imports ${specifier}`);
    }
  });
}

test("nothing raises a toast through the removed 1.4 viewport", () => {
  for (const [file, specifiers] of found) {
    assert.ok(!specifiers.includes("@plane/propel/toast"), `${file} imports @plane/propel/toast`);
  }
});

test("the comment stripper still sees a real import after a URL in a string", () => {
  const sample = 'const a = "https://example.invalid"; import { X } from "lucide-react";';
  assert.deepEqual(
    [...stripComments(sample).matchAll(LEGACY)].map((match) => match[1]),
    ["lucide-react"]
  );
});
