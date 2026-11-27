/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { readFileSync, statSync } from "node:fs";
import path from "node:path";
import ts from "typescript";
import { describe, expect, it } from "vitest";

/**
 * `@plane/editor/lib` and `@plane/editor/server` are what the live server
 * loads: the document codecs and the schema they build. Live's image installs
 * production dependencies only, so a UI package in this graph resolves there
 * only by accident of its own manifest. 0.6.0-rc.1 crash-looped when the graph
 * reached `@makeplane/propel`, whose React is a peer dependency (ledger row
 * 196); the 1.4 `@plane/propel` and `@plane/ui` still declare React as a
 * dependency and would have hidden the same mistake. The server extension set
 * is built from schema-only configs, so none of the editor's views, menus or
 * icons belong here.
 *
 * Imports are read with the TypeScript parser: `import type` and
 * `export type` are erased at build time and do not count. Under
 * `verbatimModuleSyntax` an `import { type A }` still loads its module, so it
 * counts.
 */
const SRC = path.resolve(__dirname, "../src");
const UI_PACKAGES = [
  "@makeplane/propel",
  "@plane/blocks",
  "@plane/ui",
  "@plane/propel",
  "@plane/hooks",
  "lucide-react",
  "@headlessui/react",
  "@floating-ui/react",
  "@tiptap/react",
  "react",
  "react-dom",
];
const isUiPackage = (specifier: string) =>
  UI_PACKAGES.some((name) => specifier === name || specifier.startsWith(`${name}/`));
const EXTENSIONS = ["", ".ts", ".tsx", "/index.ts", "/index.tsx"];

/** The module specifiers `source` loads at runtime. */
export const runtimeImports = (source: string, fileName = "module.ts"): string[] => {
  const file = ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, false, ts.ScriptKind.TSX);
  const specifiers: string[] = [];
  const visit = (node: ts.Node) => {
    if (ts.isImportDeclaration(node)) {
      if (!node.importClause?.isTypeOnly) specifiers.push((node.moduleSpecifier as ts.StringLiteral).text);
      return;
    }
    if (ts.isExportDeclaration(node)) {
      if (!node.isTypeOnly && node.moduleSpecifier) specifiers.push((node.moduleSpecifier as ts.StringLiteral).text);
      return;
    }
    if (
      ts.isCallExpression(node) &&
      node.expression.kind === ts.SyntaxKind.ImportKeyword &&
      node.arguments[0] &&
      ts.isStringLiteralLike(node.arguments[0])
    ) {
      specifiers.push(node.arguments[0].text);
    }
    ts.forEachChild(node, visit);
  };
  visit(file);
  return specifiers;
};

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

/** Walk the runtime import graph of `entry`; every UI package it reaches, with the import chain to it. */
const uiImports = (entry: string): { files: number; reached: string[] } => {
  const importer = new Map<string, string | null>([[entry, null]]);
  const queue = [entry];
  const reached: string[] = [];
  const chain = (file: string | null | undefined): string[] =>
    file ? [...chain(importer.get(file)), path.relative(SRC, file)] : [];
  while (queue.length > 0) {
    const file = queue.shift() as string;
    for (const specifier of runtimeImports(readFileSync(file, "utf8"), file)) {
      const local = resolveLocal(specifier, file);
      if (local) {
        if (!importer.has(local)) {
          importer.set(local, file);
          queue.push(local);
        }
      } else if (isUiPackage(specifier)) {
        reached.push(`${[...chain(file), specifier].join(" -> ")}`);
      }
    }
  }
  return { files: importer.size, reached };
};

describe("the lib and server entries of @plane/editor", () => {
  it.each(["lib.ts", "server.ts"])("%s does not reach React or UI packages", (entry) => {
    expect(uiImports(path.join(SRC, entry)).reached).toEqual([]);
  });

  it("the walker finds UI packages behind the root entry", () => {
    const { files, reached } = uiImports(path.join(SRC, "index.ts"));
    expect(files).toBeGreaterThan(100);
    const packages = new Set(reached.map((line) => line.split(" -> ").at(-1)));
    // The root entry's views and menus are Propel's; the legacy UI packages
    // are gone from the editor altogether (tests/no-legacy-ui-imports.test.ts).
    for (const name of [
      "@makeplane/propel/icons",
      "@makeplane/propel/elements/menu",
      "@floating-ui/react",
      "@tiptap/react",
      "react",
    ]) {
      expect(packages).toContain(name);
    }
  });

  it("type-only imports do not count, value imports do", () => {
    const source = [
      'import type { LucideIcon } from "lucide-react";',
      'export type { Editor } from "@tiptap/react";',
      'import { type ReactNode } from "react";',
      'import { Tooltip } from "@plane/propel/tooltip";',
      'export * from "./local";',
      'const lazy = () => import("@headlessui/react");',
    ].join("\n");
    expect(runtimeImports(source)).toEqual(["react", "@plane/propel/tooltip", "./local", "@headlessui/react"]);
  });
});
