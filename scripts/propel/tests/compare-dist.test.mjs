// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

import assert from "node:assert/strict";
import { test } from "node:test";

import { classifyDts, classifyJs, compareDist, exportedNames, sortLiteralUnions } from "../compare-dist.mjs";

const b = (text) => Buffer.from(text);

test("javascript: byte equality, then syntax trees without build comments", () => {
  const code =
    '"use client";\nimport { a } from "./a.js";\n//#region src/x.ts\nconst x = /* @__PURE__ */ a();\n//#endregion\nexport { x };\n\n//# sourceMappingURL=x.js.map';
  assert.equal(classifyJs(b(code), b(code)).category, "identical");
  const reformatted = '"use client";\nimport { a } from "./a.js";\nconst x =   /* @__PURE__ */ a();\nexport { x };';
  assert.equal(classifyJs(b(reformatted), b(code)).category, "normalized-identical");
});

test("javascript: a dropped pure annotation is a real difference", () => {
  const withPure = 'import { a } from "./a.js";\nconst x = /* @__PURE__ */ a();\nexport { x };';
  const without = 'import { a } from "./a.js";\nconst x = a();\nexport { x };';
  assert.equal(classifyJs(b(without), b(withPure)).category, "different");
});

test("javascript: reordered imports are classified, changed code is not", () => {
  const one = 'import { a } from "./a.js";\nimport { b } from "./b.js";\nexport const x = a + b;';
  const two = 'import { b } from "./b.js";\nimport { a } from "./a.js";\nexport const x = a + b;';
  assert.equal(classifyJs(b(two), b(one)).category, "import-order");
  const changed = 'import { b } from "./b.js";\nimport { a } from "./a.js";\nexport const x = a - b;';
  assert.equal(classifyJs(b(changed), b(one)).category, "different");
  const otherBinding = 'import { b as c } from "./b.js";\nimport { a } from "./a.js";\nexport const x = a + b;';
  assert.equal(classifyJs(b(otherBinding), b(one)).category, "different");
});

test("declarations: literal union order is the only accepted text difference", () => {
  const published =
    'type A = {\n  size?: "sm" | "md" | "xs" | null;\n};\nexport { A };\n//# sourceMappingURL=a.d.ts.map';
  const built = 'type A = {\n  size?: "xs" | "sm" | "md" | null;\n};\nexport { A };\n//# sourceMappingURL=a.d.ts.map';
  assert.equal(classifyDts(b(built), b(published)).category, "union-order");
  const changed = 'type A = {\n  size?: "xs" | "sm" | null;\n};\nexport { A };';
  assert.equal(classifyDts(b(changed), b(published)).category, "different");
  assert.equal(sortLiteralUnions('"b" | "a" | null'), '"a" | "b" | null');
});

test("exported names keep type markers and aliases", () => {
  assert.deepEqual(exportedNames("export { A, type B, C$1 as C, type D as E };"), ["A", "C", "type B", "type E"]);
});

test("a whole comparison fails on a missing file or a changed export list", () => {
  const published = new Map([
    ["elements/x/index.d.ts", b("export { X, type XProps };")],
    ["elements/x/index.js", b("export { X };")],
    ["styles/propel.css", b("a{}")],
  ]);
  assert.equal(compareDist(new Map(published), published).ok, true);

  const missing = new Map(published);
  missing.delete("styles/propel.css");
  const result = compareDist(missing, published);
  assert.equal(result.ok, false);
  assert.deepEqual(
    result.unexplained.map((entry) => entry.category),
    ["missing"]
  );

  const fewer = new Map(published);
  fewer.set("elements/x/index.d.ts", b("export { X };"));
  const api = compareDist(fewer, published);
  assert.equal(api.ok, false);
  assert.deepEqual(api.apiDifferences[0].missing, ["type XProps"]);
});
