#!/usr/bin/env node
/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * Walks the import graph of a built entry, such as `apps/live/dist/start.mjs`,
 * and resolves every specifier the way Node will when the server starts, from
 * the file that imports it. Workspace files (anything whose real path is not
 * inside a `node_modules` directory) are followed; a third-party package is
 * only resolved, since pnpm installed its own dependencies.
 *
 * Run against a production-only install (the live image, or the install
 * `apps/live/tests/runtime-imports.build.test.mjs` makes), it finds an import
 * that the development install satisfies through a dev or peer dependency but
 * the image does not: the crash-loop of 0.6.0-rc.1, where the editor's server
 * code reached `@makeplane/propel`, whose React is a dev and peer dependency.
 *
 * Nothing is executed. Exits 1 and lists each import that does not resolve.
 *
 *   node apps/live/scripts/check-runtime-imports.mjs apps/live/dist/start.mjs
 */

import { spawnSync } from "node:child_process";
import { readFileSync, realpathSync } from "node:fs";
import { builtinModules, createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

// Without this flag Node ignores the second argument of import.meta.resolve
// and resolves from this script instead of from the importing file.
const RESOLVE_FLAG = "--experimental-import-meta-resolve";

// `import x from "a"`, `import { a,\n b } from "a"`, `import "a"`, `export * from "a"`.
const STATIC_IMPORT = /(?:^|[;\n}])\s*(?:import|export)(?:\s*[\w$*{}\s,]*?\s*from)?\s*["']([^"'\n]+)["']/g;
const DYNAMIC_IMPORT = /\bimport\(\s*["']([^"'\n]+)["']\s*\)/g;
// CommonJS interop the bundler emits for a package it could not convert, and
// `createRequire(import.meta.url).resolve(...)` lookups such as the PDF
// exporter's font directory: `require("a")`, `require.resolve("a")` and their
// `__require` forms. A resolve that fails throws at load time just the same.
const REQUIRE = /\b(?:__)?require(?:\.resolve)?\(\s*["']([^"'\n]+)["']\s*\)/g;

const BUILTINS = new Set(builtinModules);
const isBuiltin = (specifier) =>
  specifier.startsWith("node:") || BUILTINS.has(specifier) || BUILTINS.has(specifier.split("/")[0]);

const isWorkspaceFile = (file) => !file.split(path.sep).includes("node_modules");
const isScript = (file) => /\.[cm]?js$/.test(file);

/** Every specifier `source` imports, with how it is loaded. */
export function importsOf(source) {
  const found = [];
  for (const match of source.matchAll(STATIC_IMPORT)) found.push({ specifier: match[1], kind: "import" });
  for (const match of source.matchAll(DYNAMIC_IMPORT)) found.push({ specifier: match[1], kind: "import" });
  for (const match of source.matchAll(REQUIRE)) found.push({ specifier: match[1], kind: "require" });
  return found;
}

function resolveFrom(specifier, kind, file) {
  if (kind === "require") return pathToFileURL(createRequire(file).resolve(specifier)).href;
  return import.meta.resolve(specifier, pathToFileURL(file).href);
}

/**
 * Walk the graph from `entry`. Returns the workspace files visited and every
 * import that did not resolve, as `{ importer, specifier, error }`.
 */
export function findUnresolvedImports(entry) {
  if (!process.execArgv.includes(RESOLVE_FLAG) && !(process.env.NODE_OPTIONS ?? "").includes(RESOLVE_FLAG)) {
    throw new Error(`findUnresolvedImports needs node ${RESOLVE_FLAG}`);
  }
  const queue = [realpathSync(entry)];
  const visited = new Set();
  const unresolved = [];
  while (queue.length > 0) {
    const file = queue.pop();
    if (visited.has(file)) continue;
    visited.add(file);
    for (const { specifier, kind } of importsOf(readFileSync(file, "utf8"))) {
      if (isBuiltin(specifier)) continue;
      let url;
      try {
        url = resolveFrom(specifier, kind, file);
      } catch (error) {
        unresolved.push({ importer: file, specifier, error: error.code ?? error.message });
        continue;
      }
      if (!url.startsWith("file:")) continue;
      const target = realpathSync(fileURLToPath(url));
      if (isWorkspaceFile(target) && isScript(target)) queue.push(target);
    }
  }
  return { visited: [...visited], unresolved };
}

function main(argv) {
  const entry = argv[0];
  if (!entry) {
    console.error("usage: check-runtime-imports.mjs <built entry>");
    return 2;
  }
  const { visited, unresolved } = findUnresolvedImports(path.resolve(entry));
  if (unresolved.length === 0) {
    console.log(`check-runtime-imports: ${visited.length} workspace files, every import resolves`);
    return 0;
  }
  console.error(`check-runtime-imports: ${unresolved.length} imports do not resolve from ${entry}:`);
  for (const { importer, specifier, error } of unresolved) console.error(`  ${specifier}  (${error})  in ${importer}`);
  return 1;
}

if (process.argv[1] && realpathSync(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (process.execArgv.includes(RESOLVE_FLAG)) {
    process.exitCode = main(process.argv.slice(2));
  } else {
    const child = spawnSync(process.execPath, [RESOLVE_FLAG, ...process.execArgv, ...process.argv.slice(1)], {
      stdio: "inherit",
    });
    process.exitCode = child.status ?? 1;
  }
}
