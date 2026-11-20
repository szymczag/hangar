#!/usr/bin/env node
// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

// Recover the TypeScript source of the published @makeplane/propel package
// from its npm tarball.
//
// The package ships only `dist/`, but every emitted JavaScript module carries
// a source map whose `sourcesContent` holds the original file verbatim. This
// script writes those files back out unchanged, rebuilds the few modules that
// left no source map (re-export barrels, one type-only module, one constant
// the bundler inlined), copies the stylesheets and images, and records the
// SHA-256 and origin of every file in RECOVERY.json.
//
// Usage:
//   node scripts/propel/recover.mjs --tarball <file.tgz> --integrity <sha512-…> --out <dir>
//   node scripts/propel/recover.mjs --tarball <file.tgz> --integrity <sha512-…> --out <dir> --check
//
// The run is deterministic: the same tarball always yields the same tree, and
// a second run over an existing output changes nothing. It refuses to run on
// an integrity mismatch, a path collision, a source map without
// `sourcesContent`, an unknown re-export construct, or a relative import that
// does not resolve inside the recovered tree.

import { mkdirSync, readFileSync, readdirSync, renameSync, rmSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, posix, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { parseArgs } from "node:util";

import { rebuildReexportModule, rebuildTypeModule } from "./lib/reexports.mjs";
import { RecoveryError, readPackageTarball, sha256Hex, verifyIntegrity } from "./lib/tar.mjs";

export { RecoveryError };

export const MANIFEST_NAME = "RECOVERY.json";
const GENERATOR = "scripts/propel/recover.mjs";

/** Files the bundler inlined away completely; their value is derived from the output and checked. */
const INLINED_CONSTANTS = [
  {
    path: "src/internal/dropdown-edge-gap.ts",
    name: "DROPDOWN_EDGE_GAP_PX",
  },
];

const ASSET_EXTENSIONS = new Set([".css", ".gif", ".png"]);
const SOURCE_EXTENSIONS = [".ts", ".tsx"];

function fail(message) {
  throw new RecoveryError(message);
}

function addFile(files, path, content, origin, from) {
  if (!path.startsWith("src/") && path !== "LICENSE") fail(`refusing to write outside src/: ${path}`);
  if (files.has(path)) fail(`path collision: ${path} (from ${from} and ${files.get(path).from.join(", ")})`);
  files.set(path, {
    content: Buffer.isBuffer(content) ? content : Buffer.from(content, "utf8"),
    origin,
    from: [from].flat(),
  });
}

function recoverFromSourceMaps(dist, files) {
  const mapped = new Set();
  for (const [path, buffer] of dist) {
    if (!path.startsWith("dist/") || !path.endsWith(".js.map")) continue;
    let map;
    try {
      map = JSON.parse(buffer.toString("utf8"));
    } catch {
      fail(`${path}: not valid JSON`);
    }
    if (map.version !== 3) fail(`${path}: unsupported source map version ${map.version}`);
    if (map.sourceRoot) fail(`${path}: sourceRoot is not supported`);
    if (!Array.isArray(map.sources) || map.sources.length !== 1) {
      fail(`${path}: expected exactly one source, found ${map.sources?.length ?? 0}`);
    }
    const content = map.sourcesContent?.[0];
    if (typeof content !== "string") fail(`${path}: missing sourcesContent`);
    if (!dist.has(path.replace(/\.map$/, ""))) fail(`${path}: no matching emitted module`);
    const source = posix.normalize(posix.join(posix.dirname(path), map.sources[0]));
    if (!source.startsWith("src/") || !SOURCE_EXTENSIONS.includes(posix.extname(source))) {
      fail(`${path}: unexpected source path ${map.sources[0]}`);
    }
    addFile(files, source, content, "sourcemap", path);
    mapped.add(path.replace(/\.js\.map$/, ""));
  }
  return mapped;
}

function recoverReexportModules(dist, files, mapped) {
  const distPaths = [...dist.keys()];
  const readDist = (path) => (dist.has(path) ? dist.get(path).toString("utf8") : undefined);
  const sourceByModule = new Map();
  for (const file of files.values()) {
    if (file.origin === "sourcemap")
      sourceByModule.set(file.from[0].replace(/\.map$/, ""), file.content.toString("utf8"));
  }
  const readSource = (jsPath) => sourceByModule.get(jsPath);
  for (const path of distPaths.toSorted()) {
    if (!path.startsWith("dist/") || !path.endsWith(".d.ts")) continue;
    const stem = path.replace(/\.d\.ts$/, "");
    if (mapped.has(stem)) continue;
    const jsPath = `${stem}.js`;
    const hasJs = dist.has(jsPath);
    if (hasJs && dist.has(`${jsPath}.map`)) continue;

    // What remains is a module the bundler wrote without a source map: a
    // re-export barrel (JavaScript and declarations), or a declaration with no
    // JavaScript at all, which is either a type-only module or a re-export
    // module the JavaScript graph dropped.
    const dtsText = readDist(path);
    const relative = stem.slice("dist/".length);
    const isTypeModule =
      !hasJs && !/^import \{[^}]*\} from "\.{1,2}\//m.test(dtsText) && /^(type|interface) /m.test(dtsText);
    if (isTypeModule) {
      const declarationMap = readDist(`${path}.map`);
      const mappedSource = declarationMap ? JSON.parse(declarationMap).sources?.[0] : undefined;
      if (!mappedSource) fail(`${path}: a type-only module needs a declaration map naming its source`);
      const source = posix.normalize(posix.join(posix.dirname(path), mappedSource));
      if (posix.extname(source) !== ".ts" || source !== `src/${relative}.ts`) {
        fail(`${path}: declaration map names unexpected source ${mappedSource}`);
      }
      addFile(files, source, rebuildTypeModule({ dtsPath: path, dtsText }).source, "dts", path);
      continue;
    }

    const { source } = rebuildReexportModule({
      dtsPath: path,
      dtsText,
      jsText: hasJs ? readDist(jsPath) : undefined,
      readDist,
      distPaths,
      readSource,
    });
    const target = `src/${relative}.ts`;
    addFile(files, target, source, hasJs ? "barrel" : "dts", hasJs ? [jsPath, path] : [path]);
  }

  for (const path of distPaths) {
    if (path.startsWith("dist/") && path.endsWith(".js") && !dist.has(`${path}.map`)) {
      const target = `src/${path.slice("dist/".length, -".js".length)}.ts`;
      if (!files.has(target)) fail(`${path}: emitted module without a source map was not reconstructed`);
    }
  }
}

function escapeRegExp(text) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * A constant module rolldown inlined everywhere leaves no output of its own.
 * Its value is read back from each emitted user: the identifier must be gone
 * from the module's JavaScript, and every place the source passed it as
 * `prop = NAME` or `prop={NAME}` must read `prop = <n>` or `prop: <n>` there.
 */
function recoverInlinedConstants(dist, files, inlinedConstants) {
  const constants = {};
  for (const { path, name } of inlinedConstants) {
    const specifierTail = path.replace(/^src\//, "").replace(/\.ts$/, "");
    const values = new Set();
    const users = [];
    for (const [sourcePath, file] of files) {
      if (file.origin !== "sourcemap") continue;
      const text = file.content.toString("utf8");
      const importPattern = new RegExp(
        String.raw`import \{ ${escapeRegExp(name)} \} from "(\.{1,2}/[^"]*${escapeRegExp(specifierTail.split("/").pop())})";`
      );
      const match = importPattern.exec(text);
      if (!match) continue;
      const resolved = posix.normalize(posix.join(posix.dirname(sourcePath), match[1]));
      if (resolved !== path.replace(/\.ts$/, "")) continue;
      const js = dist.get(file.from[0].replace(/\.map$/, "")).toString("utf8");
      const moduleName = `/${posix.basename(specifierTail)}.js"`;
      if (new RegExp(String.raw`\b${escapeRegExp(name)}\b`).test(js) || js.includes(moduleName)) {
        fail(`${sourcePath}: ${name} was not inlined in the emitted module`);
      }
      const uses = [...text.matchAll(new RegExp(String.raw`(\w+)\s*=\s*\{?${escapeRegExp(name)}\b`, "g"))];
      if (uses.length === 0) fail(`${sourcePath}: imports ${name} but no recognised use`);
      for (const use of uses) {
        const prop = escapeRegExp(use[1]);
        const found = [...js.matchAll(new RegExp(String.raw`\b${prop}(?: = |: )(-?\d+(?:\.\d+)?)\b`, "g"))];
        if (found.length === 0) fail(`${sourcePath}: cannot find the inlined value of ${name} for ${use[1]}`);
        for (const value of found) values.add(value[1]);
      }
      users.push(sourcePath);
    }
    if (users.length === 0) fail(`${name}: no users found`);
    if (values.size !== 1) fail(`${name}: inconsistent inlined values ${[...values].join(", ")}`);
    const [value] = values;
    constants[name] = { value: Number(value), users: users.toSorted() };
    addFile(
      files,
      path,
      `export const ${name} = ${value};\n`,
      "inlined-constant",
      users.map((user) => files.get(user).from[0].replace(/\.map$/, ""))
    );
  }
  return constants;
}

function copyAssets(dist, files) {
  for (const [path, buffer] of dist) {
    if (!path.startsWith("dist/")) continue;
    if (/\.(js|js\.map|d\.ts|d\.ts\.map)$/.test(path)) continue;
    if (!ASSET_EXTENSIONS.has(posix.extname(path))) fail(`${path}: unexpected file type in dist`);
    addFile(files, `src/${path.slice("dist/".length)}`, buffer, "copied", path);
  }
}

/** Every relative import in the recovered tree must resolve to a recovered file. */
function verifyImports(files) {
  const exists = (path) =>
    files.has(path) ||
    SOURCE_EXTENSIONS.some((extension) => files.has(`${path}${extension}`)) ||
    SOURCE_EXTENSIONS.some((extension) => files.has(`${path}/index${extension}`));
  for (const [path, file] of files) {
    if (!SOURCE_EXTENSIONS.includes(posix.extname(path))) continue;
    const text = file.content.toString("utf8");
    for (const match of text.matchAll(/(?:\bfrom|^import)\s+"(\.{1,2}\/[^"]*)"/gm)) {
      const target = posix.normalize(posix.join(posix.dirname(path), match[1]));
      if (!exists(target)) fail(`${path}: import ${match[1]} does not resolve inside the recovered tree`);
    }
  }
}

/**
 * Recover the source tree from a tarball buffer. Pure: returns the files and
 * the manifest without touching the file system.
 */
export function recover({ tarball, integrity, tarballName, inlinedConstants = INLINED_CONSTANTS }) {
  verifyIntegrity(tarball, integrity);
  const pkg = readPackageTarball(tarball);
  const manifestJson = pkg.get("package.json");
  if (!manifestJson) fail("tarball has no package.json");
  const packageJson = JSON.parse(manifestJson.toString("utf8"));
  if (packageJson.name !== "@makeplane/propel") fail(`unexpected package ${packageJson.name}`);

  const dist = new Map([...pkg].filter(([path]) => path.startsWith("dist/")));
  const files = new Map();
  const mapped = recoverFromSourceMaps(dist, files);
  recoverReexportModules(dist, files, mapped);
  const constants = recoverInlinedConstants(dist, files, inlinedConstants);
  copyAssets(dist, files);

  const license = pkg.get("LICENSE");
  if (!license) fail("tarball has no LICENSE");
  addFile(files, "LICENSE", license, "copied", "LICENSE");

  // Every declaration map must name a source that now exists.
  for (const [path, buffer] of dist) {
    if (!path.endsWith(".d.ts.map")) continue;
    const map = JSON.parse(buffer.toString("utf8"));
    for (const source of map.sources ?? []) {
      const target = posix.normalize(posix.join(posix.dirname(path), source));
      if (!files.has(target)) fail(`${path}: declaration map source ${target} was not recovered`);
    }
  }
  verifyImports(files);

  const sorted = new Map([...files].toSorted(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)));
  const counts = {};
  for (const file of sorted.values()) counts[file.origin] = (counts[file.origin] ?? 0) + 1;
  const manifest = {
    package: packageJson.name,
    version: packageJson.version,
    integrity,
    tarball: tarballName ?? `makeplane-propel-${packageJson.version}.tgz`,
    generator: GENERATOR,
    origins: {
      sourcemap: "verbatim sourcesContent of the emitted module's source map",
      barrel: "re-export module rebuilt from the emitted index.js and index.d.ts",
      dts: "module rebuilt from its emitted declaration file",
      "inlined-constant": "constant module the bundler inlined; value read back from every user",
      copied: "file copied byte for byte from the package",
    },
    constants,
    counts,
    files: [...sorted].map(([path, file]) => ({
      path,
      sha256: sha256Hex(file.content),
      origin: file.origin,
      from: file.from,
    })),
  };
  return { files: sorted, manifest };
}

export function serializeManifest(manifest) {
  return `${JSON.stringify(manifest, null, 2)}\n`;
}

function listTree(root, base = root) {
  const result = [];
  let entries;
  try {
    entries = readdirSync(root, { withFileTypes: true });
  } catch {
    return result;
  }
  for (const entry of entries) {
    const full = join(root, entry.name);
    if (entry.isDirectory()) result.push(...listTree(full, base));
    else result.push(posix.relative(base.split("\\").join("/"), full.split("\\").join("/")));
  }
  return result;
}

/** Compare a recovery result with an existing output directory; returns a list of differences. */
export function diffOutput({ files, manifest }, outDir) {
  const differences = [];
  const expected = new Map(files);
  expected.set(MANIFEST_NAME, { content: Buffer.from(serializeManifest(manifest)) });
  const present = new Set(listTree(join(outDir, "src")).map((path) => `src/${path}`));
  for (const name of ["LICENSE", MANIFEST_NAME]) {
    try {
      if (statSync(join(outDir, name)).isFile()) present.add(name);
    } catch {
      // missing
    }
  }
  for (const [path, file] of expected) {
    if (!present.has(path)) {
      differences.push(`missing: ${path}`);
      continue;
    }
    if (!readFileSync(join(outDir, path)).equals(file.content)) differences.push(`changed: ${path}`);
  }
  for (const path of present) if (!expected.has(path)) differences.push(`unexpected: ${path}`);
  return differences.toSorted();
}

/** Write the recovery result: `src/` is replaced as a whole, LICENSE and RECOVERY.json are rewritten. */
export function writeOutput({ files, manifest }, outDir) {
  const staging = join(outDir, `.recover-staging-${process.pid}`);
  rmSync(staging, { recursive: true, force: true });
  for (const [path, file] of files) {
    const target = join(staging, path);
    mkdirSync(dirname(target), { recursive: true });
    writeFileSync(target, file.content, { mode: 0o644 });
  }
  writeFileSync(join(staging, MANIFEST_NAME), serializeManifest(manifest), { mode: 0o644 });
  mkdirSync(outDir, { recursive: true });
  rmSync(join(outDir, "src"), { recursive: true, force: true });
  renameSync(join(staging, "src"), join(outDir, "src"));
  renameSync(join(staging, "LICENSE"), join(outDir, "LICENSE"));
  renameSync(join(staging, MANIFEST_NAME), join(outDir, MANIFEST_NAME));
  rmSync(staging, { recursive: true, force: true });
}

function main(argv) {
  const { values } = parseArgs({
    args: argv,
    options: {
      tarball: { type: "string" },
      integrity: { type: "string" },
      out: { type: "string" },
      check: { type: "boolean", default: false },
    },
    strict: true,
  });
  if (!values.tarball || !values.integrity || !values.out) {
    console.error("usage: recover.mjs --tarball <file.tgz> --integrity <sha512-…> --out <dir> [--check]");
    return 2;
  }
  const tarballPath = resolve(values.tarball);
  const result = recover({
    tarball: readFileSync(tarballPath),
    integrity: values.integrity,
    tarballName: posix.basename(tarballPath.split("\\").join("/")),
  });
  const outDir = resolve(values.out);
  if (values.check) {
    const differences = diffOutput(result, outDir);
    if (differences.length > 0) {
      for (const line of differences) console.error(line);
      console.error(`${differences.length} difference(s) between the tarball recovery and ${values.out}`);
      return 1;
    }
    console.log(`${values.out} matches the recovery of ${result.manifest.package}@${result.manifest.version}`);
    return 0;
  }
  writeOutput(result, outDir);
  const summary = Object.entries(result.manifest.counts)
    .map(([origin, count]) => `${count} ${origin}`)
    .join(", ");
  console.log(`recovered ${result.files.size} files into ${values.out} (${summary})`);
  return 0;
}

const invokedPath = process.argv[1] ? pathToFileURL(resolve(process.argv[1])).href : "";
if (import.meta.url === invokedPath) {
  try {
    process.exitCode = main(process.argv.slice(2));
  } catch (error) {
    if (error instanceof RecoveryError) {
      console.error(`recover: ${error.message}`);
      process.exitCode = 1;
    } else {
      throw error;
    }
  }
}
