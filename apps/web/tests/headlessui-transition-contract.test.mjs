// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const repoRoot = fileURLToPath(new URL("../../../", import.meta.url));
const webRequire = createRequire(new URL("../package.json", import.meta.url));
const ts = webRequire("typescript");
const React = webRequire("react");
const { renderToString } = webRequire("react-dom/server");
const { Transition } = webRequire("@headlessui/react");

const webSourceRoots = [path.join(repoRoot, "apps/web/app"), path.join(repoRoot, "apps/web/core")];

function walkTsxFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return walkTsxFiles(entryPath);
    return entry.isFile() && entry.name.endsWith(".tsx") ? [entryPath] : [];
  });
}

function jsxTagName(tagName) {
  return tagName.getText();
}

function isTransitionTag(tagName) {
  const name = jsxTagName(tagName);
  return name === "Transition" || name === "Transition.Child" || name === "Transition.Root";
}

function findAttribute(openingElement, attributeName) {
  return openingElement.attributes.properties.find(
    (attribute) => ts.isJsxAttribute(attribute) && attribute.name.text === attributeName
  );
}

function isFragmentAttribute(attribute) {
  if (!attribute?.initializer || !ts.isJsxExpression(attribute.initializer)) return false;
  const expression = attribute.initializer.expression;
  if (!expression) return false;
  return expression.getText() === "Fragment" || expression.getText() === "React.Fragment";
}

function isFragmentBacked(openingElement) {
  const asAttribute = findAttribute(openingElement, "as");
  return asAttribute === undefined || isFragmentAttribute(asAttribute);
}

function meaningfulChildren(element) {
  return element.children.filter((child) => {
    if (ts.isJsxText(child)) return child.getText().trim().length > 0;
    return !(ts.isJsxExpression(child) && child.expression === undefined);
  });
}

function formatLocation(sourceFile, node) {
  const position = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));
  return `${path.relative(repoRoot, sourceFile.fileName)}:${position.line + 1}`;
}

function collectUnsafeFragmentTransitions(sourceFile) {
  const violations = [];

  function visit(node) {
    if (
      ts.isJsxElement(node) &&
      isTransitionTag(node.openingElement.tagName) &&
      isFragmentBacked(node.openingElement)
    ) {
      const children = meaningfulChildren(node);
      const directFragment = children.some((child) => ts.isJsxFragment(child));

      if (children.length > 1 || directFragment) {
        violations.push(
          `${formatLocation(sourceFile, node.openingElement)} renders a Fragment-backed ${jsxTagName(
            node.openingElement.tagName
          )} with ${directFragment ? "a direct Fragment child" : `${children.length} direct children`}`
        );
      }
    }

    ts.forEachChild(node, visit);
  }

  visit(sourceFile);
  return violations;
}

test("documents the Headless UI 2 Fragment failure mode", () => {
  const unsafeTransition = React.createElement(
    Transition,
    { show: true, enter: "transition" },
    React.createElement("div", null, "loader"),
    React.createElement("div", null, "content")
  );

  assert.throws(
    () => renderToString(unsafeTransition),
    /Passing props on "Fragment"!/,
    "the regression test no longer reproduces the Headless UI contract being guarded"
  );
});

test("allows multiple children when Transition owns a DOM element", () => {
  const safeTransition = React.createElement(
    Transition,
    { as: "div", show: true, enter: "transition" },
    React.createElement("div", null, "loader"),
    React.createElement("div", null, "content")
  );

  assert.doesNotThrow(() => renderToString(safeTransition));
});

test("keeps every Fragment-backed web Transition structurally ref-safe", () => {
  const violations = webSourceRoots.flatMap(walkTsxFiles).flatMap((filePath) => {
    const source = readFileSync(filePath, "utf8");
    const sourceFile = ts.createSourceFile(filePath, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
    return collectUnsafeFragmentTransitions(sourceFile);
  });

  assert.deepEqual(violations, [], `Unsafe Headless UI Transition contracts:\n${violations.join("\n")}`);
});
