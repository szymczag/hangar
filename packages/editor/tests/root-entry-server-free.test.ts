/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { readFileSync, statSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/**
 * The root entry of @plane/editor is what the space SSR server bundle imports.
 * @tiptap/html resolves its Node condition to a server entry built on
 * happy-dom, which ships a public test private key; anything in the root
 * entry's import graph that reaches @tiptap/html inlines happy-dom into that
 * bundle (code scanning alert 181). The document codecs live in
 * `@plane/editor/lib` and `@plane/editor/server` instead.
 */
const SRC = path.resolve(__dirname, "../src");
const FORBIDDEN = /^(?:@tiptap\/html(?:\/.*)?|happy-dom(?:\/.*)?)$/;
const IMPORT = /(?:^|[\s;])(?:import|export)\s[^"'`]*?from\s*["']([^"']+)["']|import\(\s*["']([^"']+)["']\s*\)/g;
const EXTENSIONS = ["", ".ts", ".tsx", "/index.ts", "/index.tsx"];

const resolveLocal = (specifier: string, fromFile: string): string | null => {
  let base: string;
  if (specifier.startsWith("@/")) base = path.join(SRC, specifier.slice(2));
  else if (specifier.startsWith(".")) base = path.resolve(path.dirname(fromFile), specifier);
  else return null;
  for (const ext of EXTENSIONS) {
    const candidate = base + ext;
    if (statSync(candidate, { throwIfNoEntry: false })?.isFile()) return candidate;
  }
  throw new Error(`cannot resolve ${specifier} from ${fromFile}`);
};

/** Walk the static import graph of `entry` and return the package specifiers it reaches, with one importer each. */
const packageImports = (entry: string): Map<string, string> => {
  const seen = new Set<string>();
  const packages = new Map<string, string>();
  const queue = [entry];
  while (queue.length > 0) {
    const file = queue.pop() as string;
    if (seen.has(file)) continue;
    seen.add(file);
    const source = readFileSync(file, "utf8");
    for (const match of source.matchAll(IMPORT)) {
      const specifier = match[1] ?? match[2];
      const local = resolveLocal(specifier, file);
      if (local) queue.push(local);
      else if (!packages.has(specifier)) packages.set(specifier, path.relative(SRC, file));
    }
  }
  return packages;
};

describe("the root entry of @plane/editor", () => {
  it("does not reach @tiptap/html or happy-dom", () => {
    const reached = [...packageImports(path.join(SRC, "index.ts"))].filter(([specifier]) => FORBIDDEN.test(specifier));
    expect(reached).toEqual([]);
  });

  it("does not export the document codecs", () => {
    const source = readFileSync(path.join(SRC, "index.ts"), "utf8");
    expect(source).not.toMatch(/yjs-utils|document-codecs/);
  });

  it("the walker does find @tiptap/html behind the lib and server entries", () => {
    expect([...packageImports(path.join(SRC, "lib.ts")).keys()]).toContain("@tiptap/html");
    expect([...packageImports(path.join(SRC, "server.ts")).keys()]).toContain("@tiptap/html/server");
  });
});
