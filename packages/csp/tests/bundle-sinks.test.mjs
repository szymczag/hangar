/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import { SINKS, compareWithInventory, ownerOf } from "../src/bundle-sinks.mjs";

const root = "/repo";
const assets = "/repo/apps/web/build/client/assets";

test("owners are npm packages or repository paths, never versions or chunk names", () => {
  assert.equal(
    ownerOf(
      "../../../../../node_modules/.pnpm/react-dom@19.2.8_react@19.2.8/node_modules/react-dom/cjs/x.js",
      assets,
      root
    ),
    "npm:react-dom"
  );
  assert.equal(
    ownerOf(
      "../../../../../node_modules/.pnpm/@tiptap+core@2.27.3/node_modules/@tiptap/core/dist/index.js",
      assets,
      root
    ),
    "npm:@tiptap/core"
  );
  assert.equal(ownerOf("../../../../../packages/utils/dist/index.mjs", assets, root), "packages/utils");
  assert.equal(ownerOf("../../../core/hooks/use-thing.ts", assets, root), "apps/web/core/hooks/use-thing.ts");
  assert.equal(ownerOf(null, assets, root), "unmapped");
});

test("the sink patterns match assignments and calls, not reads or comparisons", () => {
  const matches = (name, code) => [...code.matchAll(SINKS.find(([sink]) => sink === name)[1])].length;
  assert.equal(matches("innerHTML", "el.innerHTML = x; el.innerHTML += y"), 2);
  assert.equal(matches("innerHTML", "const s = el.innerHTML; if (el.innerHTML === s) {}"), 0);
  assert.equal(matches("DOMParser.parseFromString", "new DOMParser().parseFromString(s, `text/html`)"), 1);
  assert.equal(matches("eval", "eval(s); new Function(s); Function(`return this`); obj.eval(s)"), 3);
});

test("new, stale and unreviewed entries are all reported", () => {
  const found = new Map([
    ["innerHTML npm:a", 1],
    ["innerHTML npm:new", 1],
  ]);
  const inventory = {
    sinks: { "innerHTML npm:a": "reason", "innerHTML npm:gone": "reason", "eval npm:x": "UNREVIEWED" },
  };
  assert.deepEqual(compareWithInventory(found, inventory), {
    unknown: ["innerHTML npm:new"],
    stale: ["eval npm:x", "innerHTML npm:gone"],
    unreviewed: ["eval npm:x"],
  });
});
