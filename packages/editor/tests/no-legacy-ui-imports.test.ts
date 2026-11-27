/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/**
 * The editor moved to Propel (`@makeplane/propel`) in three steps: the lib and
 * server entries left UI code (ledger row 201), the menus and popovers moved
 * (row 202), then the node views, tables and side-menu handles (row 203). No
 * file in `packages/editor/src` imports the four legacy packages any more:
 * `@plane/ui`, the in-repo 1.4 `@plane/propel`, Headless UI and lucide. The
 * editor no longer depends on them (package.json), so an import would resolve
 * only by accident, through another package's dependencies, and bring the 1.4
 * look back into every app that renders an editor.
 *
 * The same contract as web's (apps/web/tests/legacy-ui-imports-contract.test.mjs),
 * with an empty allowlist.
 */
const ROOT = path.resolve(__dirname, "..");
const SRC = path.join(ROOT, "src");
const LEGACY_PACKAGES = new Set(["@plane/ui", "@plane/propel", "@headlessui/react", "lucide-react"]);

function* sources(directory: string): Generator<string> {
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const full = path.join(directory, entry.name);
    if (entry.isDirectory()) yield* sources(full);
    else if (/\.(tsx?|mjs|js|css)$/.test(entry.name)) yield full;
  }
}

// Comments do not import anything; a URL inside a string is not a comment.
const stripComments = (source: string) =>
  source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:"'`\\])\/\/.*$/gm, "$1");

// `@plane/propel` is matched as a whole package name, so `@makeplane/propel` is not.
const LEGACY =
  /(?:from\s*|import\s*\(\s*|import\s+|vi\.mock\(\s*|require\(\s*|@import\s+)["'`]((?:@plane\/ui|@plane\/propel|@headlessui\/react|lucide-react)(?:\/[^"'`]*)?)["'`]/g;

const legacyImports = (source: string) => [...stripComments(source).matchAll(LEGACY)].map((match) => match[1]);

describe("packages/editor and the legacy UI packages", () => {
  const files = [...sources(SRC)];

  it("the scan reaches the editor's sources", () => {
    expect(files.length).toBeGreaterThan(200);
  });

  it("no file in packages/editor/src imports @plane/ui, @plane/propel, Headless UI or lucide", () => {
    const offenders = files.flatMap((file) => {
      const specifiers = legacyImports(readFileSync(file, "utf8"));
      return specifiers.length ? [`${path.relative(ROOT, file)}: ${[...new Set(specifiers)].join(", ")}`] : [];
    });
    expect(offenders).toEqual([]);
  });

  it("the editor declares none of them as a dependency", () => {
    const manifest = JSON.parse(readFileSync(path.join(ROOT, "package.json"), "utf8")) as Record<
      string,
      Record<string, string> | undefined
    >;
    const declared = Object.keys({
      ...manifest.dependencies,
      ...manifest.devDependencies,
      ...manifest.peerDependencies,
    });
    expect(declared.filter((name) => LEGACY_PACKAGES.has(name))).toEqual([]);
  });

  it("the matcher sees each legacy form and leaves Propel alone", () => {
    const sample = [
      'const a = "https://example.invalid"; import { X } from "lucide-react";',
      'import { Tooltip } from "@plane/propel/tooltip";',
      'import "@plane/ui/styles.css";',
      'const lazy = () => import("@headlessui/react");',
      '@import "@plane/propel/styles/fonts";',
      'import { Icon } from "@makeplane/propel/components/icon";',
      '// import { Ban } from "lucide-react";',
    ].join("\n");
    expect(legacyImports(sample)).toEqual([
      "lucide-react",
      "@plane/propel/tooltip",
      "@plane/ui/styles.css",
      "@headlessui/react",
      "@plane/propel/styles/fonts",
    ]);
  });
});
