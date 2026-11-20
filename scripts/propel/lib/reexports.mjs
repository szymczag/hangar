// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

// Reconstruction of re-export-only modules (barrels such as `index.ts`) from
// the pair of files the bundler emitted for them: `index.js` (value exports)
// and `index.d.ts` (value and type exports). Re-export-only modules carry no
// code, so the bundler wrote no source map and their source is not in any
// `sourcesContent`; their exports, however, are fully visible in the output.
//
// The scanner below is deliberately narrow. It accepts the handful of
// statement shapes the bundler emits for such modules and throws on anything
// else, so an upstream change in shape stops the recovery instead of being
// silently mistranslated.

import { posix } from "node:path";

import { RecoveryError } from "./tar.mjs";

const IDENT = String.raw`[A-Za-z_$][\w$]*`;
const IMPORT_SPEC = new RegExp(String.raw`^(${IDENT})(?: as (${IDENT}))?$`);
const EXPORT_SPEC = new RegExp(String.raw`^(type )?(${IDENT})(?: as (${IDENT}))?$`);

function splitList(list, pattern, file) {
  return list.split(",").map((raw) => {
    const item = raw.trim();
    const match = pattern.exec(item);
    if (!match) throw new RecoveryError(`${file}: unknown specifier ${JSON.stringify(item)}`);
    return match;
  });
}

/**
 * Parse the statements of an emitted re-export module (`.js` or `.d.ts`).
 * Accepted statements, one per line:
 *   "use client";
 *   import { a, b as c } from "./x.js";
 *   import "./x.js";                        (declarations only)
 *   export { a, type b, c as d };
 * Trailing `//# sourceMappingURL=` and `//#region`/`//#endregion` lines are
 * ignored. Anything else is an error.
 */
export function parseReexportFile(text, file, { allowSideEffect = false, allowTypeExports = false } = {}) {
  const imports = [];
  const sideEffects = [];
  let exports = null;
  let order = 0;
  for (const rawLine of text.split("\n")) {
    const line = rawLine.trimEnd();
    if (line === "" || line === '"use client";' || line.startsWith("//# sourceMappingURL=")) continue;
    let match;
    if ((match = /^import \{ (.+) \} from "([^"]+)";$/.exec(line))) {
      imports.push({
        order: order++,
        source: match[2],
        specifiers: splitList(match[1], IMPORT_SPEC, file).map((m) => ({ imported: m[1], local: m[2] ?? m[1] })),
      });
    } else if (allowSideEffect && (match = /^import "([^"]+)";$/.exec(line))) {
      sideEffects.push({ order: order++, source: match[1] });
    } else if ((match = /^export \{ (.*) \};?$/.exec(line))) {
      if (exports) throw new RecoveryError(`${file}: more than one export statement`);
      exports = splitList(match[1], EXPORT_SPEC, file).map((m) => {
        if (m[1] && !allowTypeExports) throw new RecoveryError(`${file}: unexpected type export ${m[2]}`);
        return { typeOnly: Boolean(m[1]), local: m[2], exported: m[3] ?? m[2] };
      });
    } else {
      throw new RecoveryError(`${file}: unknown construct ${JSON.stringify(line.slice(0, 120))}`);
    }
  }
  if (!exports) throw new RecoveryError(`${file}: no export statement`);
  return { imports, sideEffects, exports };
}

/**
 * Read the export list of any emitted declaration file. Only the final
 * `export { … };` statement and the named imports are interpreted; the
 * declarations themselves are left alone.
 */
export function parseDeclarationExports(text, file) {
  const imports = [];
  let exports = null;
  for (const rawLine of text.split("\n")) {
    const line = rawLine.trimEnd();
    let match;
    if ((match = /^import \{ (.+) \} from "([^"]+)";$/.exec(line))) {
      imports.push({
        source: match[2],
        specifiers: splitList(match[1], IMPORT_SPEC, file).map((m) => ({ imported: m[1], local: m[2] ?? m[1] })),
      });
    } else if ((match = /^export \{ (.*) \};?$/.exec(line))) {
      if (exports) throw new RecoveryError(`${file}: more than one export statement`);
      exports =
        match[1].trim() === ""
          ? []
          : splitList(match[1], EXPORT_SPEC, file).map((m) => ({
              typeOnly: Boolean(m[1]),
              local: m[2],
              exported: m[3] ?? m[2],
            }));
    }
  }
  return { imports, exports: exports ?? [] };
}

/**
 * Names a recovered TypeScript module exports, read from its source. Only the
 * statement forms the package uses are accepted; anything else is an error,
 * because a wrong export list would turn into a wrong `export *` decision.
 */
export function sourceExportNames(text, file) {
  const names = new Set();
  for (const match of text.matchAll(/^export\s+(?:type\s+)?\{([^}]*)\}/gm)) {
    for (const raw of match[1].split(",")) {
      const item = raw.trim();
      if (item === "") continue;
      const spec = /^(?:type\s+)?([A-Za-z_$][\w$]*)(?:\s+as\s+([A-Za-z_$][\w$]*))?$/.exec(item);
      if (!spec) throw new RecoveryError(`${file}: unknown export specifier ${JSON.stringify(item)}`);
      names.add(spec[2] ?? spec[1]);
    }
  }
  for (const line of text.split("\n")) {
    if (!line.startsWith("export")) continue;
    if (/^export\s+(?:type\s+)?\{/.test(line)) continue;
    const match = /^export\s+(?:async\s+)?(?:function\*?|const|type|interface)\s+([A-Za-z_$][\w$]*)/.exec(line);
    if (!match) throw new RecoveryError(`${file}: unknown export statement ${JSON.stringify(line.slice(0, 80))}`);
    names.add(match[1]);
  }
  return names;
}

function resolveFrom(file, specifier) {
  if (!specifier.startsWith("./") && !specifier.startsWith("../")) {
    throw new RecoveryError(`${file}: re-export from a package (${specifier}) is not supported`);
  }
  return posix.normalize(posix.join(posix.dirname(file), specifier));
}

/** Map each exported name of a declaration file to the module and name that declares it. */
function resolvedExports(dtsPath, parsed) {
  const jsPath = dtsPath.replace(/\.d\.ts$/, ".js");
  const locals = new Map();
  for (const entry of parsed.imports) {
    for (const specifier of entry.specifiers) {
      const module = entry.source.startsWith(".") ? resolveFrom(dtsPath, entry.source) : `package:${entry.source}`;
      locals.set(specifier.local, { module, name: specifier.imported, order: entry.order ?? 0 });
    }
  }
  return parsed.exports.map((entry) => {
    const local = locals.get(entry.local);
    return {
      ...entry,
      origin: local ? { module: local.module, name: local.name } : { module: jsPath, name: entry.exported },
      order: local ? local.order : -1,
    };
  });
}

const sameOrigin = (a, b) => a.module === b.module && a.name === b.name;

function relativeSpecifier(fromFile, target) {
  let relative = posix.relative(posix.dirname(fromFile), target);
  if (!relative.startsWith(".")) relative = `./${relative}`;
  return relative;
}

const specifierRank = (specifier) => (specifier.startsWith("../") ? 0 : 1);

function compareSpecifiers(a, b) {
  return specifierRank(a) - specifierRank(b) || (a < b ? -1 : a > b ? 1 : 0);
}

/**
 * Rebuild the TypeScript source of a re-export-only module.
 *
 * @param {object} options
 * @param {string} options.dtsPath   path of the emitted declaration file, e.g. `dist/elements/button/index.d.ts`
 * @param {string} options.dtsText   its content
 * @param {string|undefined} options.jsText  content of the emitted `.js` (absent when the bundler dropped it)
 * @param {(path: string) => string|undefined} options.readDist  reader for other emitted files
 * @param {string[]} options.distPaths  every emitted file path
 * @param {(jsPath: string) => string|undefined} options.readSource  recovered source of an emitted module
 * @returns {{ source: string, exports: string[] }}
 */
export function rebuildReexportModule({ dtsPath, dtsText, jsText, readDist, distPaths, readSource }) {
  const jsPath = dtsPath.replace(/\.d\.ts$/, ".js");
  const dts = parseReexportFile(dtsText, dtsPath, { allowSideEffect: true, allowTypeExports: true });
  const entries = resolvedExports(dtsPath, dts);

  let valueNames = null;
  const jsIndex = new Map();
  if (jsText !== undefined) {
    const js = parseReexportFile(jsText, jsPath);
    const jsLocals = new Map();
    for (const entry of js.imports) {
      for (const specifier of entry.specifiers) {
        jsLocals.set(specifier.local, { module: resolveFrom(jsPath, entry.source), name: specifier.imported });
      }
    }
    js.imports.forEach((entry, index) => jsIndex.set(resolveFrom(jsPath, entry.source), index));
    valueNames = new Set();
    for (const entry of js.exports) {
      const origin = jsLocals.get(entry.local);
      const declared = entries.find((candidate) => candidate.exported === entry.exported);
      if (!origin || !declared || !sameOrigin(origin, declared.origin) || declared.typeOnly) {
        throw new RecoveryError(`${jsPath}: value export ${entry.exported} disagrees with ${dtsPath}`);
      }
      valueNames.add(entry.exported);
    }
  }

  const exportsOf = (moduleJsPath) => {
    const path = moduleJsPath.replace(/\.js$/, ".d.ts");
    const text = readDist(path);
    if (text === undefined) return null;
    return resolvedExports(path, parseDeclarationExports(text, path)).filter((entry) => entry.exported !== "default");
  };

  // Intermediate re-export modules the declaration bundler kept as bare
  // `import "./x.js";` statements: the original source re-exported through them.
  const intermediates = dts.sideEffects.map(({ source: specifier, order }) => {
    const module = resolveFrom(dtsPath, specifier);
    const exported = exportsOf(module);
    if (!exported) throw new RecoveryError(`${dtsPath}: intermediate ${specifier} has no declaration file`);
    const isBarrel = posix.basename(module) === "index.js";
    return { module, isBarrel, directory: posix.dirname(module), exported, order };
  });

  // `export * from "./x"` re-exports every name of a sibling module with that
  // module's own type markers. A sibling whose complete export list appears
  // here, with identical markers and origins, was star-exported.
  const directory = posix.dirname(dtsPath);
  const routedThroughBarrel = (module) =>
    intermediates.some((candidate) => candidate.isBarrel && module.startsWith(`${candidate.directory}/`));
  const siblings = [
    ...new Set([
      ...distPaths
        .filter((path) => posix.dirname(path) === directory && path.endsWith(".d.ts") && path !== dtsPath)
        .map((path) => path.replace(/\.d\.ts$/, ".js")),
      ...entries.map((entry) => entry.origin.module).filter((module) => !module.startsWith("package:")),
    ]),
  ].filter((module) => module !== jsPath && !routedThroughBarrel(module));
  const covered = new Set();
  const stars = [];
  for (const module of siblings.toSorted()) {
    const exported = exportsOf(module);
    if (!exported || exported.length === 0) continue;
    // The declaration file lists only the exports something uses; the source
    // has them all. A star export re-exports every one of them.
    const source = readSource(module);
    if (source === undefined) continue;
    const declared = sourceExportNames(source, module);
    if (![...declared].every((name) => entries.some((entry) => entry.exported === name))) continue;
    const matches = exported.every((name) =>
      entries.some(
        (entry) =>
          entry.exported === name.exported && entry.typeOnly === name.typeOnly && sameOrigin(entry.origin, name.origin)
      )
    );
    if (!matches) continue;
    const own = entries.filter((entry) => entry.origin.module === module);
    const reached = entries.filter((entry) => exported.some((name) => name.exported === entry.exported));
    const order = own.length > 0 ? own[0].order : Math.max(...reached.map((entry) => entry.order));
    stars.push({ module, order, jsOrder: jsIndex.get(module) });
    for (const name of exported) covered.add(name.exported);
  }

  const groups = new Map();
  const addToGroup = (specifier, text, typeOnly, order, jsOrder) => {
    if (!groups.has(specifier)) groups.set(specifier, []);
    groups.get(specifier).push({ text, typeOnly, order, jsOrder });
  };

  for (const entry of entries) {
    if (covered.has(entry.exported)) continue;
    if (entry.origin.module.startsWith("package:")) {
      throw new RecoveryError(`${dtsPath}: re-export of ${entry.exported} from a package is not supported`);
    }
    const isValue = valueNames ? valueNames.has(entry.exported) : !entry.typeOnly;
    if (!isValue && !entry.typeOnly) {
      throw new RecoveryError(`${dtsPath}: type ${entry.exported} is exported without a type marker or export *`);
    }

    let target = entry.origin.module;
    let name = entry.origin.name;
    const via =
      intermediates.find(
        (candidate) => !candidate.isBarrel && candidate.exported.some((e) => sameOrigin(e.origin, entry.origin))
      ) ??
      intermediates.find(
        (candidate) => candidate.isBarrel && entry.origin.module.startsWith(`${candidate.directory}/`)
      );
    if (via) {
      const names = via.exported.filter((e) => sameOrigin(e.origin, entry.origin));
      if (names.length !== 1) {
        throw new RecoveryError(`${dtsPath}: cannot route ${entry.exported} through ${via.module}`);
      }
      name = names[0].exported;
      target = via.isBarrel ? via.directory : via.module.replace(/\.js$/, "");
    } else {
      target = target.replace(/\.js$/, "");
    }
    const specifier = relativeSpecifier(dtsPath, target);
    const clause = name === entry.exported ? name : `${name} as ${entry.exported}`;
    addToGroup(
      specifier,
      clause,
      !isValue,
      via ? via.order : entry.order,
      isValue ? jsIndex.get(entry.origin.module) : undefined
    );
  }

  const statements = [];
  for (const { module, order, jsOrder } of stars) {
    const specifier = relativeSpecifier(dtsPath, module.replace(/(?:\/index)?\.js$/, ""));
    statements.push({ specifier, order, jsOrder, text: `export * from "${specifier}";` });
  }
  for (const [specifier, items] of groups) {
    const allTypes = items.every((item) => item.typeOnly);
    const list = items.map((item) => (item.typeOnly && !allTypes ? `type ${item.text}` : item.text)).join(", ");
    const order = Math.min(...items.map((item) => item.order));
    const jsOrders = items.map((item) => item.jsOrder).filter((value) => value !== undefined);
    const jsOrder = jsOrders.length > 0 ? Math.min(...jsOrders) : undefined;
    statements.push({
      specifier,
      order,
      jsOrder,
      text: `export ${allTypes ? "type " : ""}{ ${list} } from "${specifier}";`,
    });
  }
  // The declaration bundler lists a module's imports in execution (post-)order,
  // and a barrel executes its re-exported modules in statement order, so the
  // position of the module a statement re-exports from gives the statement's
  // original position.
  statements.sort((a, b) => a.order - b.order || compareSpecifiers(a.specifier, b.specifier));
  // Element barrels are built before the components that import their parts,
  // so in the JavaScript graph their parts are still unvisited when the barrel
  // runs, while the declaration graph has already met some of them through type
  // imports. For those barrels the JavaScript order is the faithful one: value
  // statements follow it and type-only statements keep their declaration-order
  // position relative to them. (Chosen because it reproduces the published
  // output; see packages/makeplane-propel/README.md.)
  if (dtsPath.startsWith("dist/elements/")) {
    const ordered = statements
      .filter((statement) => statement.jsOrder !== undefined)
      .toSorted((a, b) => a.jsOrder - b.jsOrder);
    for (const statement of statements.filter((candidate) => candidate.jsOrder === undefined)) {
      let at = 0;
      ordered.forEach((placed, index) => {
        if (placed.order < statement.order) at = index + 1;
      });
      ordered.splice(at, 0, statement);
    }
    statements.splice(0, statements.length, ...ordered);
  }

  return {
    source: `${statements.map((statement) => statement.text).join("\n")}\n`,
    exports: entries.map((entry) => entry.exported),
  };
}

/**
 * Rebuild a type-only module from its emitted declaration file. Only type
 * aliases, interfaces, comments and named type imports are accepted; a
 * `declare` statement means the module had runtime code and is rejected.
 */
export function rebuildTypeModule({ dtsPath, dtsText }) {
  const lines = dtsText.split("\n");
  const out = [];
  let exported = null;
  for (const rawLine of lines) {
    const line = rawLine.trimEnd();
    if (line === '"use client";' || line.startsWith("//#region") || line === "//#endregion") continue;
    if (line.startsWith("//# sourceMappingURL=")) continue;
    let match;
    if ((match = /^export \{ (.*) \};?$/.exec(line))) {
      exported = new Set(splitList(match[1], EXPORT_SPEC, dtsPath).map((m) => m[2]));
      continue;
    }
    if (/^\s*declare\b/.test(line) || /^(const|let|var|function|class|enum)\b/.test(line)) {
      throw new RecoveryError(`${dtsPath}: not a type-only module (${line.slice(0, 60)})`);
    }
    if ((match = /^import \{ (.+) \} from "([^"]+)";$/.exec(line))) {
      out.push(`import type { ${match[1]} } from "${match[2]}";`, "");
      continue;
    }
    out.push(line);
  }
  if (!exported) throw new RecoveryError(`${dtsPath}: no export statement`);
  const source = out
    .map((line) => {
      const match = /^(type|interface) ([A-Za-z_$][\w$]*)/.exec(line);
      return match && exported.has(match[2]) ? `export ${line}` : line;
    })
    .join("\n")
    .replace(/\n*$/, "\n");
  for (const name of exported) {
    if (!new RegExp(String.raw`^export (type|interface) ${name.replace(/\$/g, "\\$")}\b`, "m").test(source)) {
      throw new RecoveryError(`${dtsPath}: exported ${name} is not declared in the module`);
    }
  }
  return { source };
}
