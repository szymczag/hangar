// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";

const webRequire = createRequire(new URL("../package.json", import.meta.url));
const ts = webRequire("typescript");
const rootPath = new URL("../app/root.tsx", import.meta.url);
const rootSource = readFileSync(rootPath, "utf8");
const sourceFile = ts.createSourceFile(rootPath.pathname, rootSource, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);

function findHydrateFallback() {
  return sourceFile.statements.find(
    (statement) => ts.isFunctionDeclaration(statement) && statement.name?.text === "HydrateFallback"
  );
}

test("keeps the SPA hydration fallback deterministic", () => {
  const hydrateFallback = findHydrateFallback();
  assert.ok(hydrateFallback?.body, "apps/web/app/root.tsx must export HydrateFallback");

  const forbiddenIdentifiers = new Set(["document", "localStorage", "sessionStorage", "useTheme", "window"]);
  const foundForbiddenIdentifiers = new Set();

  function visit(node) {
    if (ts.isIdentifier(node) && forbiddenIdentifiers.has(node.text)) {
      foundForbiddenIdentifiers.add(node.text);
    }
    ts.forEachChild(node, visit);
  }

  visit(hydrateFallback.body);

  assert.deepEqual(
    [...foundForbiddenIdentifiers].toSorted(),
    [],
    "HydrateFallback must produce the same first render in the prerenderer and browser"
  );
  assert.match(hydrateFallback.body.getText(sourceFile), /<LogoSpinner\s*\/>/);
});
