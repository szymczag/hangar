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
 *
 * Ledger row 204 then deleted `packages/ui` and `packages/propel` (upstream
 * v1.5.0 has neither), and with them the last dependant of Headless UI. Those
 * names no longer resolve anywhere, so the last tests below hold the whole
 * workspace to that: no package declares them, no source imports them, and
 * neither directory comes back. lucide stays a web-only rule; `@plane/blocks`
 * and `@plane/utils` still use it.
 */

import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = path.resolve(root, "../..");

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

test("web's stylesheet loads the Propel entry point, not the 1.4 index.css", () => {
  // Both define the same token names with different values, so loading both
  // would let whichever comes last win token by token.
  const globals = stripComments(readFileSync(path.join(root, "styles/globals.css"), "utf8"));
  assert.match(globals, /@import "@plane\/tailwind-config\/propel\.css";/);
  assert.doesNotMatch(globals, /@import "@plane\/tailwind-config\/index\.css";/);
});

// The packages that no workspace package may bring back (ledger row 204).
const REMOVED = new Set(["@plane/ui", "@plane/propel", "@headlessui/react"]);
const REMOVED_IMPORT =
  /(?:from\s*|import\s*\(\s*|import\s+|vi\.mock\(\s*|require\(\s*|@import\s+)["'`]((?:@plane\/ui|@plane\/propel|@headlessui\/react)(?:\/[^"'`]*)?)["'`]/g;
const WORKSPACE_SKIP = new Set([...SKIP, "__tests__", "coverage", "node_modules"]);

const workspaceManifests = () =>
  ["apps", "packages"].flatMap((group) =>
    readdirSync(path.join(repoRoot, group), { withFileTypes: true })
      .filter((entry) => entry.isDirectory() && existsSync(path.join(repoRoot, group, entry.name, "package.json")))
      .map((entry) => `${group}/${entry.name}`)
  );

function* workspaceSources(directory) {
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    if (WORKSPACE_SKIP.has(entry.name)) continue;
    const full = path.join(directory, entry.name);
    if (entry.isDirectory()) yield* workspaceSources(full);
    // Test files quote the names they forbid; they are not imports.
    else if (/\.(tsx?|mjs|js|css)$/.test(entry.name) && !/\.(test|spec)\./.test(entry.name)) yield full;
  }
}

test("packages/ui and packages/propel are gone from the workspace", () => {
  assert.equal(existsSync(path.join(repoRoot, "packages/ui")), false);
  assert.equal(existsSync(path.join(repoRoot, "packages/propel")), false);
  assert.ok(workspaceManifests().includes("packages/makeplane-propel"), "the scan reaches the workspace packages");
});

test("no workspace package declares @plane/ui, @plane/propel or Headless UI", () => {
  const offenders = workspaceManifests().flatMap((workspace) => {
    const manifest = JSON.parse(readFileSync(path.join(repoRoot, workspace, "package.json"), "utf8"));
    const declared = Object.keys({
      ...manifest.dependencies,
      ...manifest.devDependencies,
      ...manifest.peerDependencies,
      ...manifest.optionalDependencies,
    });
    return declared.filter((name) => REMOVED.has(name)).map((name) => `${workspace}: ${name}`);
  });
  assert.deepEqual(offenders, []);
});

test("no source in apps or packages imports @plane/ui, @plane/propel or Headless UI", () => {
  const files = workspaceManifests()
    .filter((workspace) => workspace !== "packages/makeplane-propel")
    .flatMap((workspace) => Array.from(workspaceSources(path.join(repoRoot, workspace))));
  assert.ok(files.length > 3000, "the scan reaches the workspace's sources");
  const offenders = files.flatMap((file) => {
    const specifiers = [...stripComments(readFileSync(file, "utf8")).matchAll(REMOVED_IMPORT)].map((m) => m[1]);
    return specifiers.length ? [`${path.relative(repoRoot, file)}: ${[...new Set(specifiers)].join(", ")}`] : [];
  });
  assert.deepEqual(offenders, []);
});

test("the comment stripper still sees a real import after a URL in a string", () => {
  const sample = 'const a = "https://example.invalid"; import { X } from "lucide-react";';
  assert.deepEqual(
    [...stripComments(sample).matchAll(LEGACY)].map((match) => match[1]),
    ["lucide-react"]
  );
});
