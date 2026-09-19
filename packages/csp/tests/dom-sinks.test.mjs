/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Our code turns HTML strings into DOM in exactly one place: parseInertHTML
// in @plane/utils (docs/trusted-types-plan.md, phase 1). Every other sink that
// Trusted Types guards was replaced with DOM APIs. This test keeps it that
// way: a new sink anywhere else fails here, with the file and line, instead
// of surfacing as a Trusted Types report once the policy is enforced.

import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { join, relative } from "node:path";
import { test } from "node:test";

const root = new URL("../../..", import.meta.url).pathname;
const SCANNED = ["apps/web", "apps/space", "apps/admin", "apps/live/src", "packages"];
const SKIPPED_DIRECTORIES = new Set(["node_modules", "dist", "build", "tests", ".turbo", "public", ".react-router"]);
const SOURCE = /\.(ts|tsx|js|jsx|mjs)$/;

// The one sink our code is allowed. Phase 2 gives it the only Trusted Types
// policy our code needs.
const ALLOWED = new Map([["packages/utils/src/inert-html.ts", ["new DOMParser"]]]);

const SINKS = [
  ["innerHTML assignment", /\.innerHTML\s*[+]?=(?!=)/],
  ["outerHTML assignment", /\.outerHTML\s*[+]?=(?!=)/],
  ["insertAdjacentHTML", /\binsertAdjacentHTML\s*\(/],
  ["new DOMParser", /\bnew\s+DOMParser\b/],
  ["document.write", /\bdocument\.write(ln)?\s*\(/],
  ["dangerouslySetInnerHTML", /\bdangerouslySetInnerHTML\b/],
  ["createContextualFragment", /\bcreateContextualFragment\s*\(/],
  ["srcdoc assignment", /\.srcdoc\s*=(?!=)|\bsrcDoc\s*=/],
  ["setHTMLUnsafe / parseHTMLUnsafe", /\b(setHTMLUnsafe|parseHTMLUnsafe)\s*\(/],
];

function* sourceFiles(directory) {
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      if (!SKIPPED_DIRECTORIES.has(entry.name)) yield* sourceFiles(join(directory, entry.name));
    } else if (SOURCE.test(entry.name) && !/\.(test|spec)\./.test(entry.name)) {
      yield join(directory, entry.name);
    }
  }
}

test("DOM sinks that Trusted Types guards appear only in parseInertHTML", () => {
  const found = [];
  const allowedSeen = new Set();
  for (const scanned of SCANNED) {
    for (const file of sourceFiles(join(root, scanned))) {
      const path = relative(root, file);
      readFileSync(file, "utf8")
        .split("\n")
        .forEach((line, index) => {
          for (const [name, pattern] of SINKS) {
            if (!pattern.test(line)) continue;
            if (ALLOWED.get(path)?.includes(name)) {
              allowedSeen.add(path);
              continue;
            }
            found.push(`${path}:${index + 1}  ${name}`);
          }
        });
    }
  }
  assert.deepEqual(
    found,
    [],
    `Build the DOM with DOM APIs (createElement, createElementNS, textContent) ` +
      `or parse through parseInertHTML from @plane/utils. See docs/trusted-types-plan.md.\n${found.join("\n")}`
  );
  // The allowance must still be needed; an unused one is a stale exception.
  assert.deepEqual([...allowedSeen], [...ALLOWED.keys()]);
});
