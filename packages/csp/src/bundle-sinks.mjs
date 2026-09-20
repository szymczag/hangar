/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Trusted Types bundle contract (docs/trusted-types-plan.md, phase 3).
//
//   hangar-bundle-sinks --assets apps/web/build/client/assets --inventory packages/csp/bundle-sinks/web.json
//
// Lists every DOM sink that Trusted Types guards in a built bundle, maps each
// one through the (hidden) source maps to the npm package or repository file
// it came from, and compares the result with a reviewed inventory. A sink from
// a new owner, an inventory entry nothing matches any more, and an entry
// without a reason all fail. `--update` rewrites the inventory, keeping the
// reasons already written and marking new entries UNREVIEWED, which still
// fails until someone writes down why the sink is acceptable.
//
// Keys are "<sink> <owner>", without line numbers or chunk names, so they only
// change when a sink or an owner does, not on every build. Build the bundle
// with HANGAR_BUNDLE_SOURCEMAPS=1.

import { existsSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { parseArgs } from "node:util";

import { SourceMapConsumer } from "source-map-js";

export const SINKS = [
  ["innerHTML", /\.innerHTML\s*[+]?=(?!=)/g],
  ["outerHTML", /\.outerHTML\s*[+]?=(?!=)/g],
  ["insertAdjacentHTML", /\.insertAdjacentHTML\(/g],
  ["document.write", /\bdocument\.write(?:ln)?\(/g],
  ["DOMParser.parseFromString", /\.parseFromString\(/g],
  ["createContextualFragment", /\.createContextualFragment\(/g],
  ["srcdoc", /\.srcdoc\s*=(?!=)/g],
  ["setHTMLUnsafe", /\.(?:setHTMLUnsafe|parseHTMLUnsafe)\(/g],
  ["dangerouslySetInnerHTML", /\b__html\b/g],
  ["script element", /createElement\(\s*[`"']script[`"']\s*\)/g],
  ["Worker", /\bnew\s+(?:Shared)?Worker\(/g],
  ["eval", /(?<![\w$.])eval\(|\bnew\s+Function\(|(?<![\w$.])Function\(\s*[`"']/g],
];

const UNREVIEWED = "UNREVIEWED";

const repositoryRoot = (start) => {
  let directory = resolve(start);
  while (!existsSync(join(directory, "pnpm-workspace.yaml"))) {
    const parent = dirname(directory);
    if (parent === directory) throw new Error(`no pnpm-workspace.yaml above ${start}`);
    directory = parent;
  }
  return directory;
};

/** npm package name, or the repository path (packages' dist collapsed to the package). */
export const ownerOf = (source, assetsDirectory, root) => {
  if (!source) return "unmapped";
  const absolute = resolve(assetsDirectory, source.replace(/^webpack:\/\/\//, ""));
  const segments = absolute.split("/node_modules/");
  if (segments.length > 1) {
    const packagePath = segments.at(-1).split("/");
    return `npm:${packagePath[0].startsWith("@") ? `${packagePath[0]}/${packagePath[1]}` : packagePath[0]}`;
  }
  const path = relative(root, absolute);
  const dist = /^(packages\/[^/]+)\/dist\//.exec(path);
  return dist ? dist[1] : path;
};

export const scanBundle = (assetsDirectory) => {
  const root = repositoryRoot(assetsDirectory);
  const found = new Map();
  let mappedFiles = 0;
  for (const file of readdirSync(assetsDirectory).filter((name) => name.endsWith(".js"))) {
    const code = readFileSync(join(assetsDirectory, file), "utf8");
    const mapPath = join(assetsDirectory, `${file}.map`);
    const consumer = existsSync(mapPath) ? new SourceMapConsumer(JSON.parse(readFileSync(mapPath, "utf8"))) : null;
    if (consumer) mappedFiles += 1;
    // Files the build generates itself (React Router's manifest, Vite's preload
    // helper, re-export stubs) have no source map; they are named by file,
    // without the content hash.
    const generatedOwner = `generated:${file.replace(/-[\w-]{8}\.js$/, "").replace(/\.js$/, "")}`;
    const lineStarts = [0];
    for (let index = code.indexOf("\n"); index !== -1; index = code.indexOf("\n", index + 1))
      lineStarts.push(index + 1);
    for (const [sink, pattern] of SINKS) {
      for (const match of code.matchAll(pattern)) {
        let line = 0;
        while (line + 1 < lineStarts.length && lineStarts[line + 1] <= match.index) line += 1;
        const position = consumer?.originalPositionFor({ line: line + 1, column: match.index - lineStarts[line] });
        const owner = consumer ? ownerOf(position?.source, assetsDirectory, root) : generatedOwner;
        const key = `${sink} ${owner}`;
        found.set(key, (found.get(key) ?? 0) + 1);
      }
    }
  }
  return { found, mappedFiles };
};

export const compareWithInventory = (found, inventory) => {
  const known = inventory.sinks ?? {};
  return {
    unknown: [...found.keys()].filter((key) => !(key in known)).toSorted(),
    stale: Object.keys(known)
      .filter((key) => !found.has(key))
      .toSorted(),
    unreviewed: Object.entries(known)
      .filter(([, reason]) => !reason || reason === UNREVIEWED)
      .map(([key]) => key)
      .toSorted(),
  };
};

export const main = () => {
  const { values } = parseArgs({
    options: { assets: { type: "string" }, inventory: { type: "string" }, update: { type: "boolean" } },
  });
  if (!values.assets || !values.inventory) {
    console.error("usage: hangar-bundle-sinks --assets <dir> --inventory <file.json> [--update]");
    process.exit(2);
  }
  const { found, mappedFiles } = scanBundle(values.assets);
  if (mappedFiles === 0) {
    console.error(`hangar-bundle-sinks: ${values.assets} has no source maps; build with HANGAR_BUNDLE_SOURCEMAPS=1`);
    process.exit(2);
  }
  const inventory = existsSync(values.inventory) ? JSON.parse(readFileSync(values.inventory, "utf8")) : { sinks: {} };

  if (values.update) {
    const sinks = Object.fromEntries(
      [...found.keys()].toSorted().map((key) => [key, inventory.sinks?.[key] || UNREVIEWED])
    );
    writeFileSync(values.inventory, `${JSON.stringify({ ...inventory, sinks }, null, 2)}\n`);
    console.log(`hangar-bundle-sinks: wrote ${Object.keys(sinks).length} entries to ${values.inventory}`);
    return;
  }

  const { unknown, stale, unreviewed } = compareWithInventory(found, inventory);
  const problems = [
    ...unknown.map((key) => `new sink, not in the inventory: ${key}`),
    ...stale.map((key) => `in the inventory, no longer in the bundle: ${key}`),
    ...unreviewed.map((key) => `in the inventory without a reason: ${key}`),
  ];
  if (problems.length > 0) {
    console.error(
      `hangar-bundle-sinks: ${values.assets} does not match ${values.inventory}.\n` +
        `A new sink must go through a Trusted Types policy; see docs/trusted-types-plan.md, then run with --update and write the reason.\n  ` +
        problems.join("\n  ")
    );
    process.exit(1);
  }
  console.log(`hangar-bundle-sinks: ${found.size} sink owner(s) in ${values.assets}, all reviewed`);
};
