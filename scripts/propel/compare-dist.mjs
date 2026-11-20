#!/usr/bin/env node
// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

// Compare the `dist/` built from the recovered @makeplane/propel source with
// the `dist/` of the published npm tarball.
//
// Levels:
//   1. file set     the same paths, maps included;
//   2. JavaScript   parsed with acorn and compared as syntax trees, with the
//                   remaining comments (pure annotations, JSDoc) compared in
//                   order; `//#region`, `//#endregion` and `sourceMappingURL`
//                   comments and all whitespace are ignored;
//   3. source maps  the `sources` and `sourcesContent` of every map must be
//                   identical, which shows each module was built from the
//                   very text the published one was built from;
//   4. declarations compared as text after the same normalization, plus the
//                   exported names (with type markers) of every public subpath;
//   5. styles and images byte for byte.
//
// Every file lands in one category. Only the categories listed in EXPLAINED
// are accepted; anything else makes the run fail. Each accepted category
// carries the reason it cannot change behaviour.
//
// Usage:
//   node scripts/propel/compare-dist.mjs --built <dist> --published <dist> [--report <file.md>] [--json <file.json>]
//   node scripts/propel/compare-dist.mjs --built <dist> --tarball <file.tgz> --integrity <sha512-…> [...]

import { readFileSync, readdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join, posix, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { parseArgs } from "node:util";

import { RecoveryError, readPackageTarball, verifyIntegrity } from "./lib/tar.mjs";

const PACKAGE_DIR = fileURLToPath(new URL("../../packages/makeplane-propel/", import.meta.url));

/** Accepted, explained categories of difference. */
export const EXPLAINED = {
  "import-order": {
    kind: "js",
    reason:
      "Same import declarations with the same bindings, in a different order; the module bodies are " +
      "identical syntax trees. The order follows the bundler's global execution order, which depends " +
      "on statement order inside the re-export barrels that the build did not publish. No module in the " +
      "package does anything at load time beyond creating its own values (cva class builders, React " +
      "contexts, `displayName` on its own components), and the package declares " +
      '`"sideEffects": ["**/*.css"]`, so the order in which a module\'s dependencies are evaluated ' +
      "cannot change behaviour; consuming bundlers reorder modules anyway.",
  },
  "union-order": {
    kind: "dts",
    reason:
      "Same declarations, but members of string-literal union types are listed in a different order " +
      '(e.g. `"sm" | "md" | "xs"` against `"xs" | "sm" | "md"`). TypeScript prints a union in the ' +
      "order it first created each literal type, and the declaration plugin emits modules in the " +
      "order they finish loading, which is not deterministic: identical builds differ from each other " +
      "in the same way. A union is unordered, so the types are identical.",
  },
};

const IDENTICAL = new Set(["identical", "normalized-identical"]);

function loadAcorn() {
  const require = createRequire(join(PACKAGE_DIR, "package.json"));
  return require("acorn");
}

function listFiles(root, base = root) {
  const files = [];
  for (const entry of readdirSync(root, { withFileTypes: true })) {
    const full = join(root, entry.name);
    if (entry.isDirectory()) files.push(...listFiles(full, base));
    else files.push(posix.relative(base.split("\\").join("/"), full.split("\\").join("/")));
  }
  return files;
}

export function readDistDirectory(root) {
  return new Map(listFiles(root).map((path) => [path, readFileSync(join(root, path))]));
}

export function readDistTarball(buffer, integrity) {
  verifyIntegrity(buffer, integrity);
  const files = new Map();
  for (const [path, content] of readPackageTarball(buffer)) {
    if (path.startsWith("dist/")) files.set(path.slice("dist/".length), content);
  }
  return files;
}

const BUILD_COMMENT = /^(?:#region\b.*|#endregion\s*|# sourceMappingURL=.*)$/;

const POSITION_KEYS = new Set(["start", "end", "loc", "range", "raw"]);

/** Copy a syntax tree without positions or raw source text, with keys sorted. */
function stripPositions(node) {
  if (Array.isArray(node)) return node.map(stripPositions);
  if (node && typeof node === "object") {
    const out = {};
    for (const key of Object.keys(node).toSorted()) {
      if (!POSITION_KEYS.has(key)) out[key] = stripPositions(node[key]);
    }
    return out;
  }
  return node;
}

const isImport = (node) => node.type === "ImportDeclaration";
const nodeKey = (node) => JSON.stringify(node);

/** Parse JavaScript into a position-free tree plus the comments that carry meaning. */
export function normalizeJs(code, acorn = loadAcorn()) {
  const comments = [];
  const tree = acorn.parse(code, {
    ecmaVersion: "latest",
    sourceType: "module",
    onComment: (block, text) => {
      if (!block && BUILD_COMMENT.test(text.trim())) return;
      comments.push(`${block ? "block" : "line"}:${text.replace(/\s+/g, " ").trim()}`);
    },
  });
  return { tree: stripPositions(tree), comments };
}

function sameJson(a, b) {
  return JSON.stringify(a) === JSON.stringify(b);
}

export function classifyJs(built, published, acorn = loadAcorn()) {
  if (built.equals(published)) return { category: "identical" };
  let a;
  let b;
  try {
    a = normalizeJs(built.toString("utf8"), acorn);
    b = normalizeJs(published.toString("utf8"), acorn);
  } catch (error) {
    return { category: "different", detail: `parse error: ${error.message}` };
  }
  if (sameJson(a, b)) return { category: "normalized-identical" };
  if (!sameJson(a.comments, b.comments)) return { category: "different", detail: "comments differ" };

  if (
    sameJson(
      a.tree.body.filter((node) => !isImport(node)),
      b.tree.body.filter((node) => !isImport(node))
    ) &&
    sameJson(
      a.tree.body.filter(isImport).map(nodeKey).toSorted(),
      b.tree.body.filter(isImport).map(nodeKey).toSorted()
    ) &&
    // Only the order among the import declarations may differ, not where they sit.
    sameJson(a.tree.body.map(isImport), b.tree.body.map(isImport))
  ) {
    return { category: "import-order" };
  }
  return { category: "different", detail: "syntax trees differ" };
}

/** Text normalization for declarations: build comments and whitespace go. */
export function normalizeDts(text) {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line !== "" && !/^\/\/(?:#region\b|#endregion\b|# sourceMappingURL=)/.test(line))
    .join("\n")
    .replace(/[ \t]+/g, " ");
}

/** Sort every run of two or more string-literal union members. */
export function sortLiteralUnions(text) {
  return text.replace(/"(?:[^"\\\n]|\\.)*"(?: \| "(?:[^"\\\n]|\\.)*")+/g, (run) =>
    run.split(" | ").toSorted().join(" | ")
  );
}

export function classifyDts(built, published) {
  if (built.equals(published)) return { category: "identical" };
  const a = normalizeDts(built.toString("utf8"));
  const b = normalizeDts(published.toString("utf8"));
  if (a === b) return { category: "normalized-identical" };
  if (sortLiteralUnions(a) === sortLiteralUnions(b)) return { category: "union-order" };
  return { category: "different", detail: "declaration text differs" };
}

export function exportedNames(dtsText) {
  const match = /^export \{ (.*) \};?$/m.exec(dtsText);
  if (!match) return [];
  return match[1]
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => {
      const spec = /^(type )?([\w$]+)(?: as ([\w$]+))?$/.exec(item);
      return spec ? `${spec[1] ? "type " : ""}${spec[3] ?? spec[2]}` : `?${item}`;
    })
    .toSorted();
}

function classifyMap(built, published) {
  if (built.equals(published)) return { category: "identical" };
  let a;
  let b;
  try {
    a = JSON.parse(built.toString("utf8"));
    b = JSON.parse(published.toString("utf8"));
  } catch {
    return { category: "different", detail: "map is not JSON" };
  }
  if (!sameJson(a.sources, b.sources)) return { category: "different", detail: "map sources differ" };
  if (!sameJson(a.sourcesContent ?? null, b.sourcesContent ?? null)) {
    return { category: "different", detail: "map sourcesContent differs" };
  }
  // Mappings follow the generated code; they are not compared.
  return { category: "normalized-identical" };
}

export function kindOf(path) {
  if (path.endsWith(".js.map") || path.endsWith(".d.ts.map")) return "map";
  if (path.endsWith(".d.ts")) return "dts";
  if (path.endsWith(".js")) return "js";
  return "asset";
}

/** Public subpaths whose declaration entry points carry the package's API. */
function publicDeclarations(paths) {
  return paths.filter((path) => /^(?:(?:base|elements|components|hooks)\/[^/]+|icons)\/index\.d\.ts$/.test(path));
}

export function compareDist(built, published, { acorn = loadAcorn() } = {}) {
  const results = [];
  const all = [...new Set([...built.keys(), ...published.keys()])].toSorted();
  for (const path of all) {
    const kind = kindOf(path);
    if (!built.has(path)) {
      results.push({ path, kind, category: "missing" });
      continue;
    }
    if (!published.has(path)) {
      results.push({ path, kind, category: "extra" });
      continue;
    }
    const a = built.get(path);
    const b = published.get(path);
    let result;
    if (kind === "js") result = classifyJs(a, b, acorn);
    else if (kind === "dts") result = classifyDts(a, b);
    else if (kind === "map") result = classifyMap(a, b);
    else result = a.equals(b) ? { category: "identical" } : { category: "different", detail: "bytes differ" };
    results.push({ path, kind, ...result });
  }

  const apiDifferences = [];
  for (const path of publicDeclarations([...published.keys()])) {
    if (!built.has(path)) continue;
    const a = exportedNames(built.get(path).toString("utf8"));
    const b = exportedNames(published.get(path).toString("utf8"));
    if (!sameJson(a, b)) {
      apiDifferences.push({
        path,
        missing: b.filter((name) => !a.includes(name)),
        extra: a.filter((name) => !b.includes(name)),
      });
    }
  }

  const unexplained = results.filter(
    (result) =>
      !IDENTICAL.has(result.category) &&
      !(EXPLAINED[result.category] && EXPLAINED[result.category].kind === result.kind)
  );
  return {
    results,
    apiDifferences,
    publicSubpaths: publicDeclarations([...published.keys()]).length,
    ok: unexplained.length === 0 && apiDifferences.length === 0,
    unexplained,
  };
}

function summarize(comparison) {
  const table = {};
  for (const result of comparison.results) {
    table[result.kind] ??= {};
    table[result.kind][result.category] = (table[result.kind][result.category] ?? 0) + 1;
  }
  return table;
}

export function renderReport(comparison, { builtLabel, publishedLabel }) {
  const table = summarize(comparison);
  const categories = [...new Set(comparison.results.map((result) => result.category))].toSorted();
  const lines = [];
  lines.push("# @makeplane/propel dist equivalence report", "");
  lines.push(`- built: \`${builtLabel}\``, `- published: \`${publishedLabel}\``);
  lines.push(`- files compared: ${comparison.results.length}`);
  lines.push(`- public declaration entry points checked for exported names: ${comparison.publicSubpaths}`);
  lines.push(`- result: **${comparison.ok ? "equivalent" : "NOT equivalent"}**`, "");
  lines.push(`| kind | ${categories.join(" | ")} |`, `| --- | ${categories.map(() => "---:").join(" | ")} |`);
  for (const kind of ["js", "dts", "map", "asset"]) {
    if (!table[kind]) continue;
    lines.push(`| ${kind} | ${categories.map((category) => table[kind][category] ?? 0).join(" | ")} |`);
  }
  lines.push("");
  lines.push(
    "`identical`: byte for byte. `normalized-identical`: equal after dropping `//#region`/`//#endregion`/" +
      "`sourceMappingURL` comments and whitespace (JavaScript compared as syntax trees plus the remaining " +
      "comments; source maps compared by `sources` and `sourcesContent`).",
    ""
  );
  for (const [category, { reason }] of Object.entries(EXPLAINED)) {
    const files = comparison.results.filter((result) => result.category === category);
    if (files.length === 0) continue;
    lines.push(`## Accepted: ${category} (${files.length})`, "", reason, "");
    for (const file of files) lines.push(`- \`${file.path}\``);
    lines.push("");
  }
  if (comparison.apiDifferences.length > 0) {
    lines.push("## Exported names that differ", "");
    for (const difference of comparison.apiDifferences) {
      lines.push(
        `- \`${difference.path}\`: missing ${difference.missing.join(", ") || "-"}; extra ${difference.extra.join(", ") || "-"}`
      );
    }
    lines.push("");
  }
  if (comparison.unexplained.length > 0) {
    lines.push("## Unexplained differences", "");
    for (const result of comparison.unexplained) {
      lines.push(
        `- \`${result.path}\` (${result.kind}): ${result.category}${result.detail ? ` - ${result.detail}` : ""}`
      );
    }
    lines.push("");
  }
  return `${lines.join("\n")}`;
}

function main(argv) {
  const { values } = parseArgs({
    args: argv,
    options: {
      built: { type: "string" },
      published: { type: "string" },
      tarball: { type: "string" },
      integrity: { type: "string" },
      report: { type: "string" },
      json: { type: "string" },
    },
    strict: true,
  });
  if (!values.built || (!values.published && !(values.tarball && values.integrity))) {
    console.error(
      "usage: compare-dist.mjs --built <dist> (--published <dist> | --tarball <file.tgz> --integrity <sha512-…>) " +
        "[--report <file.md>] [--json <file.json>]"
    );
    return 2;
  }
  const built = readDistDirectory(resolve(values.built));
  const published = values.published
    ? readDistDirectory(resolve(values.published))
    : readDistTarball(readFileSync(resolve(values.tarball)), values.integrity);
  const comparison = compareDist(built, published);
  const report = renderReport(comparison, {
    builtLabel: values.built,
    publishedLabel: values.published ?? `${posix.basename(values.tarball)} (${values.integrity.slice(0, 19)}…)`,
  });
  if (values.report) writeFileSync(values.report, report);
  if (values.json) {
    writeFileSync(
      values.json,
      `${JSON.stringify({ ok: comparison.ok, summary: summarize(comparison), results: comparison.results, apiDifferences: comparison.apiDifferences }, null, 2)}\n`
    );
  }
  console.log(report);
  return comparison.ok ? 0 : 1;
}

const invokedPath = process.argv[1] ? pathToFileURL(resolve(process.argv[1])).href : "";
if (import.meta.url === invokedPath) {
  try {
    process.exitCode = main(process.argv.slice(2));
  } catch (error) {
    if (error instanceof RecoveryError) {
      console.error(`compare-dist: ${error.message}`);
      process.exitCode = 1;
    } else {
      throw error;
    }
  }
}
