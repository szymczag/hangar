/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import { SINKS, compareWithInventory, ownerOf, scanBundle } from "../src/bundle-sinks.mjs";

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

test("a chunk with a sink but no source map is reported, not attributed to its own file name", () => {
  // The flake this closes: chunk names are build output, so naming an unmapped
  // chunk after itself made the inventory gain and lose entries between runs,
  // and the check passed or failed depending on which artifacts were lying
  // around. Such a file is now named to the caller instead.
  const directory = mkdtempSync(join(tmpdir(), "bundle-sinks-"));
  writeFileSync(join(directory, "pnpm-workspace.yaml"), "packages: []\n");
  const assetsDirectory = join(directory, "assets");
  mkdirSync(assetsDirectory);
  writeFileSync(join(assetsDirectory, "mapped-a1b2c3d4.js"), "el.innerHTML = x;\n");
  writeFileSync(
    join(assetsDirectory, "mapped-a1b2c3d4.js.map"),
    JSON.stringify({ version: 3, sources: ["../../core/thing.ts"], names: [], mappings: "AAAA" })
  );
  writeFileSync(join(assetsDirectory, "root-e5f6a7b8.js"), "el.innerHTML = y;\n");

  const { found, unmappedWithSinks } = scanBundle(assetsDirectory);

  assert.deepEqual(unmappedWithSinks, ["root-e5f6a7b8.js"]);
  assert.equal(
    [...found.keys()].some((key) => key.includes("generated:")),
    false
  );

  rmSync(directory, { recursive: true, force: true });
});
