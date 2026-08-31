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
const tailwindVariablesPath = path.join(repoRoot, "packages/tailwind-config/variables.css");
const tailwindStylesPath = path.join(repoRoot, "packages/tailwind-config/index.css");
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

function isSingleElementExpression(expression, sourceFile, visitedIdentifiers = new Set()) {
  if (
    ts.isParenthesizedExpression(expression) ||
    ts.isAsExpression(expression) ||
    ts.isNonNullExpression(expression) ||
    ts.isSatisfiesExpression(expression)
  ) {
    return isSingleElementExpression(expression.expression, sourceFile, visitedIdentifiers);
  }

  if (ts.isJsxElement(expression) || ts.isJsxSelfClosingElement(expression)) return true;

  if (ts.isConditionalExpression(expression)) {
    return (
      isSingleElementExpression(expression.whenTrue, sourceFile, visitedIdentifiers) &&
      isSingleElementExpression(expression.whenFalse, sourceFile, visitedIdentifiers)
    );
  }

  // `{element}` where `const element = <div />` is declared in the same file.
  if (ts.isIdentifier(expression) && sourceFile) {
    if (visitedIdentifiers.has(expression.text)) return false;
    const initializer = findVariableInitializer(sourceFile, expression.text);
    if (!initializer || ts.isArrowFunction(initializer) || ts.isFunctionExpression(initializer)) return false;

    return isSingleElementExpression(initializer, sourceFile, new Set([...visitedIdentifiers, expression.text]));
  }

  // `{renderPanel()}` where `const renderPanel = () => <div />` is declared in the same file.
  if (
    ts.isCallExpression(expression) &&
    ts.isIdentifier(expression.expression) &&
    expression.arguments.length === 0 &&
    sourceFile
  ) {
    const name = expression.expression.text;
    if (visitedIdentifiers.has(name)) return false;

    const initializer = findVariableInitializer(sourceFile, name);
    if (!initializer || !(ts.isArrowFunction(initializer) || ts.isFunctionExpression(initializer))) return false;

    const returned = returnedExpression(initializer);
    return returned ? isSingleElementExpression(returned, sourceFile, new Set([...visitedIdentifiers, name])) : false;
  }

  return false;
}

function isStaticallySingleElement(child, sourceFile) {
  if (ts.isJsxElement(child) || ts.isJsxSelfClosingElement(child)) return true;
  if (!ts.isJsxExpression(child) || !child.expression) return false;
  return isSingleElementExpression(child.expression, sourceFile);
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

      // A Fragment-backed Transition always forwards a ref, so its child must be exactly one
      // statically verifiable element. `{flag && <Panel />}` satisfies "one child" but renders
      // `false` during the leave transition, which throws `Passing props on "Fragment"!`.
      if (children.length !== 1 || !isStaticallySingleElement(children[0], sourceFile)) {
        const reason = directFragment
          ? "a direct Fragment child"
          : children.length !== 1
            ? `${children.length} direct children`
            : "a child that is not statically verifiable as a single element";

        violations.push(
          `${formatLocation(sourceFile, node.openingElement)} renders a Fragment-backed ${jsxTagName(
            node.openingElement.tagName
          )} with ${reason}`
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

      if (children.length !== 1 || !isStaticallySingleElement(children[0], sourceFile)) {
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

      if (children.length !== 1 || !isStaticallySingleElement(children[0], sourceFile)) {
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
      node.initializer.expression?.getText(sourceFile).includes("setPopperElement")
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

function collectUnsafePopperPanelLayers(sourceFile) {
  const violations = [];
  const imports = headlessUiImports(sourceFile);
  const hasManualPortal =
    sourceFile.text.includes("createPortal(") || sourceFile.text.includes("ReactDOM.createPortal(");

  function visit(node) {
    const openingElement = ts.isJsxElement(node)
      ? node.openingElement
      : ts.isJsxSelfClosingElement(node)
        ? node
        : undefined;

    if (openingElement && isHeadlessUiPositioningPanelTag(openingElement.tagName, imports)) {
      const refAttribute = findAttribute(openingElement, "ref");
      const refExpression =
        refAttribute?.initializer && ts.isJsxExpression(refAttribute.initializer)
          ? refAttribute.initializer.expression?.getText(sourceFile)
          : undefined;

      if (refExpression?.includes("setPopperElement")) {
        const panelName = jsxTagName(openingElement.tagName);
        const className = findAttribute(openingElement, "className")?.getText(sourceFile) ?? "";

        if (findAttribute(openingElement, "portal") === undefined && !hasManualPortal) {
          violations.push(
            `${formatLocation(sourceFile, openingElement)} positions ${panelName} inside a clipping ancestor instead of a portal`
          );
        }

        if (findAttribute(openingElement, "data-prevent-outside-click") === undefined) {
          violations.push(
            `${formatLocation(sourceFile, openingElement)} does not protect portaled ${panelName} interactions from outside-click handlers`
          );
        }

        if (!className.includes("z-")) {
          violations.push(
            `${formatLocation(sourceFile, openingElement)} leaves positioned ${panelName} without an explicit stacking layer`
          );
        }
      }
    }

    ts.forEachChild(node, visit);
  }

  visit(sourceFile);
  return violations;
}

function collectPopperTargetsWithoutRuntimePlacement(sourceFile) {
  const violations = [];

  function visit(node) {
    const openingElement = ts.isJsxElement(node)
      ? node.openingElement
      : ts.isJsxSelfClosingElement(node)
        ? node
        : undefined;

    if (openingElement) {
      const refAttribute = findAttribute(openingElement, "ref");
      const refExpression =
        refAttribute?.initializer && ts.isJsxExpression(refAttribute.initializer)
          ? refAttribute.initializer.expression?.getText(sourceFile)
          : undefined;

      if (refExpression?.includes("setPopperElement")) {
        const spreadsPopperAttributes = openingElement.attributes.properties.some(
          (attribute) =>
            ts.isJsxSpreadAttribute(attribute) && attribute.expression.getText(sourceFile) === "attributes.popper"
        );

        if (!spreadsPopperAttributes) {
          violations.push(
            `${formatLocation(sourceFile, openingElement)} does not expose Popper's runtime placement attribute required by the global floating-overlay layer`
          );
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

test("documents the collapsing-disclosure Fragment failure mode", () => {
  // The shape that crashed the sidebar: `<Transition show={flag}>{flag && <Panel />}</Transition>`.
  // While the leave transition plays, `show` is already false, so the only child evaluates to
  // `false` and Headless UI has nothing to forward its ref to.
  const collapsing = React.createElement(Transition, { show: true, enter: "transition" }, false);

  assert.throws(
    () => renderToString(collapsing),
    /Passing props on "Fragment"!/,
    "the regression test no longer reproduces the collapsing-disclosure crash being guarded"
  );
});

test("allows a Transition to own a single always-rendered panel", () => {
  // The fix: no conditional guard, so the Transition always has exactly one element child and
  // owns mounting itself through `show`.
  const safe = React.createElement(
    Transition,
    { show: true, enter: "transition" },
    React.createElement("div", null, "panel")
  );

  assert.doesNotThrow(() => renderToString(safe));
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

test("keeps shared loading primitives able to receive a Headless UI ref", () => {
  // A Fragment-backed Transition forwards a ref and asserts it landed on a DOM node in an effect
  // ("Did you forget to passthrough the `ref` to the actual DOM node?"). That throw cannot be
  // reproduced through renderToString because effects do not run during SSR, so guard the source
  // shape instead: Loader is rendered directly inside a Transition by the rich-filters row.
  const loaderSource = readFileSync(path.join(repoRoot, "packages/ui/src/loader.tsx"), "utf8");

  assert.match(
    loaderSource,
    /React\.forwardRef</,
    "Loader must forward refs so Headless UI can attach to its DOM node"
  );
  assert.match(loaderSource, /<div\s+ref=\{ref\}/, "Loader must attach the forwarded ref to its root element");
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

test("keeps Popper-backed Headless UI panels visible and interactive outside clipping ancestors", () => {
  const violations = sourceRoots.flatMap(walkTsxFiles).flatMap((filePath) => {
    const source = readFileSync(filePath, "utf8");
    const sourceFile = ts.createSourceFile(filePath, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
    return collectUnsafePopperPanelLayers(sourceFile);
  });

  assert.deepEqual(violations, [], `Unsafe Headless UI Popper layers:\n${violations.join("\n")}`);
});

test("keeps every Popper target above application dialogs", () => {
  const violations = sourceRoots.flatMap(walkTsxFiles).flatMap((filePath) => {
    const source = readFileSync(filePath, "utf8");
    const sourceFile = ts.createSourceFile(filePath, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
    return collectPopperTargetsWithoutRuntimePlacement(sourceFile);
  });

  assert.deepEqual(
    violations,
    [],
    `Popper targets without the shared floating-overlay layer:\n${violations.join("\n")}`
  );

  const variables = readFileSync(tailwindVariablesPath, "utf8");
  const styles = readFileSync(tailwindStylesPath, "utf8");

  assert.match(variables, /--z-index-floating-overlay:\s*110\s*;/);
  assert.match(
    styles,
    /\[data-popper-placement\]\s*\{[^}]*z-index:\s*var\(--z-index-floating-overlay\)\s*!important\s*;/s
  );
});
