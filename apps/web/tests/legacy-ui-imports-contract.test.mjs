// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

/**
 * Web moved to Propel (`@makeplane/propel`) and `@plane/blocks` in phases 0-9.
 * After phase 9b no file in web imports the four legacy packages: `@plane/ui`,
 * the in-repo `@plane/propel`, Headless UI and lucide. Web no longer depends on
 * them at all (package.json), so an import would only resolve by accident,
 * through another package's dependencies, and would bring the 1.4 look back.
 *
 * `@plane/editor` still draws some 1.4 components of its own; that is the
 * editor's dependency, not web's, and is not counted here.
 *
 * A `setToast` from `@plane/propel/toast` is the sharpest case: its viewport is
 * gone from the provider, so that toast would show nowhere.
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

const found = new Map();
for (const file of sources(root)) {
  const relative = path.relative(root, file).split(path.sep).join("/");
  const specifiers = [...stripComments(readFileSync(file, "utf8")).matchAll(LEGACY)].map((match) => match[1]);
  if (specifiers.length) found.set(relative, [...new Set(specifiers)].toSorted());
}

test("the scan reaches web's sources", () => {
  assert.ok([...sources(root)].length > 1500);
});

test("no file in web imports @plane/ui, @plane/propel, Headless UI or lucide", () => {
  const offenders = [...found].map(([file, specifiers]) => `${file}: ${specifiers.join(", ")}`);
  assert.deepEqual(offenders, [], `move these to @makeplane/propel or @plane/blocks:\n${offenders.join("\n")}`);
});

test("web declares none of them as a dependency", () => {
  const manifest = JSON.parse(readFileSync(path.join(root, "package.json"), "utf8"));
  const declared = Object.keys({ ...manifest.dependencies, ...manifest.devDependencies });
  const legacy = declared.filter((name) =>
    ["@plane/ui", "@plane/propel", "@headlessui/react", "lucide-react"].includes(name)
  );
  assert.deepEqual(legacy, []);
});

test("no stylesheet in web imports the 1.4 packages' styles", () => {
  const styles = path.join(root, "styles");
  for (const entry of readdirSync(styles).filter((name) => name.endsWith(".css"))) {
    const source = stripComments(readFileSync(path.join(styles, entry), "utf8"));
    assert.doesNotMatch(source, /@import\s+["'](?:@plane\/ui|@plane\/propel)\//, `styles/${entry}`);
  }
});

test("the comment stripper still sees a real import after a URL in a string", () => {
  const sample = 'const a = "https://example.invalid"; import { X } from "lucide-react";';
  assert.deepEqual(
    [...stripComments(sample).matchAll(LEGACY)].map((match) => match[1]),
    ["lucide-react"]
  );
});
