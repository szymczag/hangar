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
const { Combobox, Transition } = webRequire("@headlessui/react");

const sourceRoots = [path.join(repoRoot, "apps"), path.join(repoRoot, "packages")];
const fragmentButtonComponents = new Set(["Combobox", "Disclosure", "Listbox", "Menu", "Popover"]);
const nonModalPanelComponents = new Map([
  ["Combobox", "Options"],
  ["Listbox", "Options"],
  ["Menu", "Items"],
]);
const positionedPanelComponents = new Map([...nonModalPanelComponents, ["Popover", "Panel"]]);

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

function headlessUiImports(sourceFile) {
  const imports = new Map();

  for (const statement of sourceFile.statements) {
    if (
      !ts.isImportDeclaration(statement) ||
      !ts.isStringLiteral(statement.moduleSpecifier) ||
      statement.moduleSpecifier.text !== "@headlessui/react" ||
      !statement.importClause?.namedBindings ||
      !ts.isNamedImports(statement.importClause.namedBindings)
    ) {
      continue;
    }

    for (const element of statement.importClause.namedBindings.elements) {
      imports.set(element.name.text, element.propertyName?.text ?? element.name.text);
    }
  }

  return imports;
}

function isFragmentButtonTag(tagName, imports) {
  const name = jsxTagName(tagName);
  const [rootName, memberName] = name.split(".");
  const importedRootName = imports.get(rootName);

  if (memberName === "Button" && fragmentButtonComponents.has(importedRootName)) return true;

  const importedName = imports.get(name);
  return importedName !== undefined && [...fragmentButtonComponents].some((root) => importedName === `${root}Button`);
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

function isExplicitFragmentBacked(openingElement) {
  return isFragmentAttribute(findAttribute(openingElement, "as"));
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

function isSingleElementExpression(expression) {
  if (
    ts.isParenthesizedExpression(expression) ||
    ts.isAsExpression(expression) ||
    ts.isNonNullExpression(expression) ||
    ts.isSatisfiesExpression(expression)
  ) {
    return isSingleElementExpression(expression.expression);
  }

  if (ts.isJsxElement(expression) || ts.isJsxSelfClosingElement(expression)) return true;

  if (ts.isConditionalExpression(expression)) {
    return isSingleElementExpression(expression.whenTrue) && isSingleElementExpression(expression.whenFalse);
  }

  return false;
}

function isStaticallySingleElement(child) {
  if (ts.isJsxElement(child) || ts.isJsxSelfClosingElement(child)) return true;
  if (!ts.isJsxExpression(child) || !child.expression) return false;
  return isSingleElementExpression(child.expression);
}

function findVariableInitializer(sourceFile, variableName) {
  let initializer;

  function visit(node) {
    if (
      initializer === undefined &&
      ts.isVariableDeclaration(node) &&
      ts.isIdentifier(node.name) &&
      node.name.text === variableName
    ) {
      initializer = node.initializer;
      return;
    }

    ts.forEachChild(node, visit);
  }

  visit(sourceFile);
  return initializer;
}

function returnedExpression(functionExpression) {
  if (!ts.isBlock(functionExpression.body)) return functionExpression.body;

  const returnStatement = functionExpression.body.statements.find(
    (statement) => ts.isReturnStatement(statement) && statement.expression
  );
  return returnStatement?.expression;
}

function isNativeButtonExpression(expression, sourceFile, visitedIdentifiers = new Set()) {
  if (
    ts.isParenthesizedExpression(expression) ||
    ts.isAsExpression(expression) ||
    ts.isNonNullExpression(expression) ||
    ts.isSatisfiesExpression(expression)
  ) {
    return isNativeButtonExpression(expression.expression, sourceFile, visitedIdentifiers);
  }

  if (ts.isJsxElement(expression)) return jsxTagName(expression.openingElement.tagName) === "button";
  if (ts.isJsxSelfClosingElement(expression)) return jsxTagName(expression.tagName) === "button";

  if (ts.isConditionalExpression(expression)) {
    return (
      isNativeButtonExpression(expression.whenTrue, sourceFile, visitedIdentifiers) &&
      isNativeButtonExpression(expression.whenFalse, sourceFile, visitedIdentifiers)
    );
  }

  if (ts.isIdentifier(expression)) {
    if (visitedIdentifiers.has(expression.text)) return false;
    const initializer = findVariableInitializer(sourceFile, expression.text);
    if (!initializer) return false;

    return isNativeButtonExpression(initializer, sourceFile, new Set([...visitedIdentifiers, expression.text]));
  }

  if (
    ts.isCallExpression(expression) &&
    expression.expression.getText(sourceFile) === "useMemo" &&
    expression.arguments[0] &&
    (ts.isArrowFunction(expression.arguments[0]) || ts.isFunctionExpression(expression.arguments[0]))
  ) {
    const returned = returnedExpression(expression.arguments[0]);
    return returned ? isNativeButtonExpression(returned, sourceFile, visitedIdentifiers) : false;
  }

  return false;
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

function collectUnsafeFragmentButtons(sourceFile) {
  const violations = [];
  const imports = headlessUiImports(sourceFile);

  function visit(node) {
    if (
      ts.isJsxElement(node) &&
      isFragmentButtonTag(node.openingElement.tagName, imports) &&
      isExplicitFragmentBacked(node.openingElement)
    ) {
      const children = meaningfulChildren(node);

      if (children.length !== 1 || !isStaticallySingleElement(children[0])) {
        violations.push(
          `${formatLocation(sourceFile, node.openingElement)} renders ${jsxTagName(
            node.openingElement.tagName
          )} as Fragment without one statically verifiable element child`
        );
      }
    }

    ts.forEachChild(node, visit);
  }

  visit(sourceFile);
  return violations;
}

function collectUnsafeFragmentPanels(sourceFile) {
  const violations = [];
  const imports = headlessUiImports(sourceFile);

  function visit(node) {
    if (
      ts.isJsxElement(node) &&
      isHeadlessUiPositioningPanelTag(node.openingElement.tagName, imports) &&
      isExplicitFragmentBacked(node.openingElement)
    ) {
      const children = meaningfulChildren(node);

      if (children.length !== 1 || !isStaticallySingleElement(children[0])) {
        violations.push(
          `${formatLocation(sourceFile, node.openingElement)} renders ${jsxTagName(
            node.openingElement.tagName
          )} as Fragment without one statically verifiable element child`
        );
      }
    }

    ts.forEachChild(node, visit);
  }

  visit(sourceFile);
  return violations;
}

function collectUnsafeComboDropDownButtons(sourceFile) {
  const violations = [];

  function visit(node) {
    if (ts.isJsxElement(node) && jsxTagName(node.openingElement.tagName) === "ComboDropDown") {
      const buttonAttribute = findAttribute(node.openingElement, "button");
      const expression =
        buttonAttribute?.initializer && ts.isJsxExpression(buttonAttribute.initializer)
          ? buttonAttribute.initializer.expression
          : undefined;

      if (!expression || !isNativeButtonExpression(expression, sourceFile)) {
        violations.push(
          `${formatLocation(sourceFile, node.openingElement)} passes a trigger that is not statically verified as a native button`
        );
      }
    }

    ts.forEachChild(node, visit);
  }

  visit(sourceFile);
  return violations;
}

function isHeadlessUiPanelTag(tagName, imports) {
  const name = jsxTagName(tagName);
  const [rootName, memberName] = name.split(".");
  const importedRootName = imports.get(rootName);

  if (importedRootName && memberName && nonModalPanelComponents.get(importedRootName) === memberName) return true;

  const importedName = imports.get(name);
  return [...nonModalPanelComponents].some(
    ([componentName, panelName]) => importedName === `${componentName}${panelName}`
  );
}

function isHeadlessUiPositioningPanelTag(tagName, imports) {
  const name = jsxTagName(tagName);
  const [rootName, memberName] = name.split(".");
  const importedRootName = imports.get(rootName);

  if (importedRootName && memberName && positionedPanelComponents.get(importedRootName) === memberName) return true;

  const importedName = imports.get(name);
  return [...positionedPanelComponents].some(
    ([componentName, panelName]) => importedName === `${componentName}${panelName}`
  );
}

function isFalseAttribute(attribute) {
  if (!attribute?.initializer || !ts.isJsxExpression(attribute.initializer)) return false;
  return attribute.initializer.expression?.kind === ts.SyntaxKind.FalseKeyword;
}

function collectModalLegacyPanels(sourceFile) {
  const violations = [];
  const imports = headlessUiImports(sourceFile);

  function visit(node) {
    const openingElement = ts.isJsxElement(node)
      ? node.openingElement
      : ts.isJsxSelfClosingElement(node)
        ? node
        : undefined;

    if (openingElement && isHeadlessUiPanelTag(openingElement.tagName, imports)) {
      const modalAttribute = findAttribute(openingElement, "modal");

      if (!isFalseAttribute(modalAttribute)) {
        violations.push(
          `${formatLocation(sourceFile, openingElement)} must explicitly use modal={false} to preserve the Headless UI 1 dropdown contract`
        );
      }
    }

    ts.forEachChild(node, visit);
  }

  visit(sourceFile);
  return violations;
}

function collectUnsynchronizedComboDropDowns(sourceFile) {
  const violations = [];

  function visit(node) {
    const openingElement = ts.isJsxElement(node)
      ? node.openingElement
      : ts.isJsxSelfClosingElement(node)
        ? node
        : undefined;

    if (
      openingElement &&
      jsxTagName(openingElement.tagName) === "ComboDropDown" &&
      findAttribute(openingElement, "onClose") === undefined
    ) {
      violations.push(
        `${formatLocation(sourceFile, openingElement)} must synchronize Headless UI's internal close with external dropdown state`
      );
    }

    ts.forEachChild(node, visit);
  }

  visit(sourceFile);
  return violations;
}

function collectNestedPopperTargets(sourceFile) {
  const violations = [];
  const imports = headlessUiImports(sourceFile);

  function visit(node) {
    if (
      ts.isJsxAttribute(node) &&
      node.name.text === "ref" &&
      node.initializer &&
      ts.isJsxExpression(node.initializer) &&
      node.initializer.expression?.getText(sourceFile) === "setPopperElement"
    ) {
      const owner = node.parent.parent;
      if (!isHeadlessUiPositioningPanelTag(owner.tagName, imports)) {
        let ancestor = owner.parent;

        while (ancestor) {
          if (ts.isJsxElement(ancestor) && isHeadlessUiPositioningPanelTag(ancestor.openingElement.tagName, imports)) {
            violations.push(
              `${formatLocation(sourceFile, node)} attaches Popper to a descendant of ${jsxTagName(
                ancestor.openingElement.tagName
              )}; Headless UI 2 requires the panel root to own the positioning ref`
            );
            break;
          }

          ancestor = ancestor.parent;
        }
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

test("documents the Headless UI 2 Fragment button failure mode", () => {
  const unsafeButton = React.createElement(
    Combobox,
    null,
    React.createElement(
      Combobox.Button,
      { as: React.Fragment },
      React.createElement(
        React.Fragment,
        null,
        React.createElement("button", { type: "button" }, "first"),
        React.createElement("button", { type: "button" }, "second")
      )
    )
  );

  assert.throws(
    () => renderToString(unsafeButton),
    /Passing props on "Fragment"!/,
    "the regression test no longer reproduces the Headless UI button contract being guarded"
  );
});

test("allows Headless UI to own the Combobox button element", () => {
  const safeButton = React.createElement(
    Combobox,
    null,
    React.createElement(Combobox.Button, { type: "button" }, "open")
  );

  assert.doesNotThrow(() => renderToString(safeButton));
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

test("keeps every Fragment-backed Transition structurally ref-safe", () => {
  const violations = sourceRoots.flatMap(walkTsxFiles).flatMap((filePath) => {
    const source = readFileSync(filePath, "utf8");
    const sourceFile = ts.createSourceFile(filePath, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
    return collectUnsafeFragmentTransitions(sourceFile);
  });

  assert.deepEqual(violations, [], `Unsafe Headless UI Transition contracts:\n${violations.join("\n")}`);
});

test("keeps every Fragment-backed Headless UI button structurally ref-safe", () => {
  const violations = sourceRoots.flatMap(walkTsxFiles).flatMap((filePath) => {
    const source = readFileSync(filePath, "utf8");
    const sourceFile = ts.createSourceFile(filePath, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
    return collectUnsafeFragmentButtons(sourceFile);
  });

  assert.deepEqual(violations, [], `Unsafe Headless UI button contracts:\n${violations.join("\n")}`);
});

test("keeps every Fragment-backed Headless UI panel structurally ref-safe", () => {
  const violations = sourceRoots.flatMap(walkTsxFiles).flatMap((filePath) => {
    const source = readFileSync(filePath, "utf8");
    const sourceFile = ts.createSourceFile(filePath, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
    return collectUnsafeFragmentPanels(sourceFile);
  });

  assert.deepEqual(violations, [], `Unsafe Headless UI panel contracts:\n${violations.join("\n")}`);
});

test("keeps every ComboDropDown trigger structurally ref-safe", () => {
  const violations = sourceRoots.flatMap(walkTsxFiles).flatMap((filePath) => {
    const source = readFileSync(filePath, "utf8");
    const sourceFile = ts.createSourceFile(filePath, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
    return collectUnsafeComboDropDownButtons(sourceFile);
  });

  assert.deepEqual(violations, [], `Unsafe ComboDropDown button contracts:\n${violations.join("\n")}`);
});

test("keeps legacy Headless UI dropdown panels non-modal", () => {
  const violations = sourceRoots.flatMap(walkTsxFiles).flatMap((filePath) => {
    const source = readFileSync(filePath, "utf8");
    const sourceFile = ts.createSourceFile(filePath, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
    return collectModalLegacyPanels(sourceFile);
  });

  assert.deepEqual(violations, [], `Unsafe modal Headless UI dropdown panels:\n${violations.join("\n")}`);
});

test("keeps ComboDropDown internal and external close state synchronized", () => {
  const violations = sourceRoots.flatMap(walkTsxFiles).flatMap((filePath) => {
    const source = readFileSync(filePath, "utf8");
    const sourceFile = ts.createSourceFile(filePath, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
    return collectUnsynchronizedComboDropDowns(sourceFile);
  });

  assert.deepEqual(violations, [], `Unsynchronized ComboDropDown contracts:\n${violations.join("\n")}`);
});

test("keeps Popper refs on Headless UI 2 panel roots", () => {
  const violations = sourceRoots.flatMap(walkTsxFiles).flatMap((filePath) => {
    const source = readFileSync(filePath, "utf8");
    const sourceFile = ts.createSourceFile(filePath, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
    return collectNestedPopperTargets(sourceFile);
  });

  assert.deepEqual(violations, [], `Unsafe nested Headless UI Popper targets:\n${violations.join("\n")}`);
});
