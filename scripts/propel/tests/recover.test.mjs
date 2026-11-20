// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

import assert from "node:assert/strict";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import { rebuildReexportModule, rebuildTypeModule, sourceExportNames } from "../lib/reexports.mjs";
import { RecoveryError, readPackageTarball, verifyIntegrity } from "../lib/tar.mjs";
import { diffOutput, recover, writeOutput } from "../recover.mjs";
import { makeTarball, samplePackage, sourceMap } from "./helpers.mjs";

const run = (pkg, options = {}) => recover({ ...pkg, inlinedConstants: [], ...options });

test("reads a tarball and strips the package/ prefix", () => {
  const files = readPackageTarball(makeTarball([["package/a/b.txt", "hello"]]));
  assert.deepEqual([...files.keys()], ["a/b.txt"]);
  assert.equal(files.get("a/b.txt").toString(), "hello");
});

test("refuses unsafe tar entries", () => {
  assert.throws(() => readPackageTarball(makeTarball([["package/../evil", "x"]])), RecoveryError);
  assert.throws(() => readPackageTarball(makeTarball([["/etc/passwd", "x"]])), RecoveryError);
  assert.throws(() => readPackageTarball(makeTarball([["other/file", "x"]])), /outside package/);
  assert.throws(() => readPackageTarball(makeTarball([["package/link", "", "2"]])), /unsupported tar entry type/);
  assert.throws(
    () =>
      readPackageTarball(
        makeTarball([
          ["package/a", "1"],
          ["package/a", "2"],
        ])
      ),
    /duplicate tar entry/
  );
});

test("refuses a tarball whose sha512 does not match", () => {
  const pkg = samplePackage();
  assert.throws(() => verifyIntegrity(pkg.tarball, `sha512-${"A".repeat(86)}==`), /integrity mismatch/);
  assert.throws(() => verifyIntegrity(pkg.tarball, "sha1-abc"), /SRI sha512/);
  assert.throws(
    () => run({ ...pkg, integrity: samplePackage({ "package/LICENSE": "other\n" }).integrity }),
    /integrity/
  );
});

test("recovers sources, barrels, type-only modules and assets", () => {
  const { files, manifest } = run(samplePackage());
  assert.deepEqual(
    [...files.keys()],
    [
      "LICENSE",
      "src/elements/button/button.tsx",
      "src/elements/button/index.ts",
      "src/internal/size.ts",
      "src/styles/propel.css",
    ]
  );
  assert.match(files.get("src/elements/button/button.tsx").content.toString(), /export function Button/);
  assert.equal(files.get("src/elements/button/index.ts").content.toString(), 'export * from "./button";\n');
  assert.equal(
    files.get("src/internal/size.ts").content.toString(),
    'export type Size = "sm" | "md";\n'.replace(/^/, "/** A size. */\n")
  );
  assert.deepEqual(manifest.counts, { copied: 2, sourcemap: 1, barrel: 1, dts: 1 });
  for (const file of manifest.files) assert.match(file.sha256, /^[0-9a-f]{64}$/);
});

test("refuses a source map without sourcesContent", () => {
  const pkg = samplePackage({
    "package/dist/elements/button/button.js.map": sourceMap("button.js", "../../../src/elements/button/button.tsx"),
  });
  assert.throws(() => run(pkg), /missing sourcesContent/);
});

test("refuses a path collision", () => {
  const pkg = samplePackage({
    "package/dist/elements/button/copy.js": "function x() {}\nexport { x };\n",
    "package/dist/elements/button/copy.js.map": sourceMap("copy.js", "../../../src/elements/button/button.tsx", "x"),
  });
  assert.throws(() => run(pkg), /path collision: src\/elements\/button\/button\.tsx/);
});

test("refuses a source outside src/", () => {
  const pkg = samplePackage({
    "package/dist/elements/button/button.js.map": sourceMap("button.js", "../../../../outside.tsx", "x"),
  });
  assert.throws(() => run(pkg), /unexpected source path/);
});

test("refuses an unknown construct in a barrel", () => {
  const pkg = samplePackage({
    "package/dist/elements/button/index.js": '"use client";\nexport default 1;\n',
  });
  assert.throws(() => run(pkg), /unknown construct/);
});

test("refuses an import that does not resolve inside the recovered tree", () => {
  const pkg = samplePackage({
    "package/dist/elements/button/button.js.map": sourceMap(
      "button.js",
      "../../../src/elements/button/button.tsx",
      'import { missing } from "./missing";\nexport function Button() {}\n'
    ),
  });
  assert.throws(() => run(pkg), /does not resolve/);
});

test("recovers an inlined constant only when every user agrees", () => {
  const user = (value) => ({
    "package/dist/elements/button/button.js": `function Button({ gap = ${value} }) {}\nexport { Button };\n`,
    "package/dist/elements/button/button.js.map": sourceMap(
      "button.js",
      "../../../src/elements/button/button.tsx",
      'import type { Size } from "../../internal/size";\nimport { GAP } from "../../internal/gap";\n\nexport type ButtonProps = { size: Size };\nexport function Button({ gap = GAP }: { gap?: number }) {}\n'
    ),
  });
  const inlinedConstants = [{ path: "src/internal/gap.ts", name: "GAP" }];
  const { files, manifest } = run(samplePackage(user(16)), { inlinedConstants });
  assert.equal(files.get("src/internal/gap.ts").content.toString(), "export const GAP = 16;\n");
  assert.deepEqual(manifest.constants.GAP, { value: 16, users: ["src/elements/button/button.tsx"] });

  const notInlined = samplePackage({
    ...user(16),
    "package/dist/elements/button/button.js": 'import { GAP } from "../../internal/gap.js";\nexport { GAP };\n',
  });
  assert.throws(() => run(notInlined, { inlinedConstants }), /was not inlined/);
});

test("writes deterministically and a second run changes nothing", () => {
  const out = mkdtempSync(join(tmpdir(), "propel-recover-"));
  try {
    const result = run(samplePackage());
    writeOutput(result, out);
    const first = readFileSync(join(out, "RECOVERY.json"), "utf8");
    assert.deepEqual(diffOutput(run(samplePackage()), out), []);
    writeOutput(run(samplePackage()), out);
    assert.equal(readFileSync(join(out, "RECOVERY.json"), "utf8"), first);

    writeFileSync(join(out, "src/elements/button/index.ts"), "edited\n");
    writeFileSync(join(out, "src/stray.ts"), "x\n");
    assert.deepEqual(diffOutput(result, out), ["changed: src/elements/button/index.ts", "unexpected: src/stray.ts"]);
    writeOutput(result, out);
    assert.equal(existsSync(join(out, "src/stray.ts")), false);
  } finally {
    rmSync(out, { recursive: true, force: true });
  }
});

const readDist = (files) => (path) => files[path];

test("barrels: sibling modules whose whole export list is re-exported become export *", () => {
  const files = {
    "dist/el/a.d.ts": "type AProps = {};\ndeclare function A(): void;\nexport { A, AProps };",
    "dist/el/b.d.ts": "declare const b: number;\nexport { b };",
  };
  const sources = {
    "dist/el/a.js": "export type AProps = {};\nexport function A() {}\n",
    "dist/el/b.js": "export const b = 1;\nexport const unused = 2;\n",
  };
  const { source } = rebuildReexportModule({
    dtsPath: "dist/el/index.d.ts",
    dtsText: 'import { A, AProps } from "./a.js";\nimport { b } from "./b.js";\nexport { A, AProps, b };',
    jsText: 'import { A } from "./a.js";\nimport { b } from "./b.js";\nexport { A, b };',
    readDist: readDist(files),
    distPaths: Object.keys(files),
    readSource: (path) => sources[path],
  });
  assert.equal(source, 'export * from "./a";\nexport { b } from "./b";\n');
});

test("barrels: names reached through another barrel keep aliases and type markers", () => {
  const files = {
    "dist/el/x/index.d.ts": 'import { X, XProps } from "./x.js";\nexport { X, XProps };',
    "dist/el/x/x.d.ts": "type XProps = {};\ndeclare function X(): void;\nexport { X, XProps };",
  };
  const { source } = rebuildReexportModule({
    dtsPath: "dist/comp/x/index.d.ts",
    dtsText:
      '"use client";\nimport { X as X$1, XProps } from "../../el/x/x.js";\nimport "../../el/x/index.js";\nexport { X$1 as XPart, type XProps };',
    jsText: '"use client";\nimport { X as X$1 } from "../../el/x/x.js";\nexport { X$1 as XPart };',
    readDist: readDist(files),
    distPaths: Object.keys(files),
    readSource: () => undefined,
  });
  assert.equal(source, 'export { X as XPart, type XProps } from "../../el/x";\n');
});

test("barrels: a type exported without marker and without a star source is rejected", () => {
  assert.throws(
    () =>
      rebuildReexportModule({
        dtsPath: "dist/el/index.d.ts",
        dtsText: 'import { T } from "./t.js";\nexport { T };',
        jsText: "export {  };",
        readDist: () => undefined,
        distPaths: [],
        readSource: () => undefined,
      }),
    RecoveryError
  );
});

test("type-only modules are rebuilt from declarations and must not declare values", () => {
  const { source } = rebuildTypeModule({
    dtsPath: "dist/t.d.ts",
    dtsText:
      'import { V } from "pkg";\n//#region src/t.d.ts\ntype A<T> = V<T>;\ninterface B {}\n//#endregion\nexport { A };',
  });
  assert.equal(source, 'import type { V } from "pkg";\n\nexport type A<T> = V<T>;\ninterface B {}\n');
  assert.throws(
    () => rebuildTypeModule({ dtsPath: "dist/t.d.ts", dtsText: "declare const a: 1;\nexport { a };" }),
    /not a type-only module/
  );
});

test("source export names cover the forms the package uses and reject others", () => {
  const names = sourceExportNames(
    'export function f() {}\nexport const c = 1;\nexport type T = 1;\nexport interface I {}\nexport type {\n  A,\n  B as C,\n} from "./x";\nexport { d, type e as E };\n',
    "x.ts"
  );
  assert.deepEqual([...names].toSorted(), ["C", "A", "E", "I", "T", "c", "d", "f"].toSorted());
  assert.throws(() => sourceExportNames("export default 1;\n", "x.ts"), /unknown export statement/);
});
