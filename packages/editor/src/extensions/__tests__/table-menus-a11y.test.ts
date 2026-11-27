/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Extension } from "@tiptap/core";
import { Editor } from "@tiptap/react";
import { StarterKit } from "@tiptap/starter-kit";
import { act, createElement } from "react";
import { createRoot } from "react-dom/client";
import type { Root } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";
import { Table, TableCell, TableHeader, TableRow } from "@/extensions/table";
import { ColumnDragHandle } from "@/extensions/table/plugins/drag-handles/column/drag-handle";
import { RowDragHandle } from "@/extensions/table/plugins/drag-handles/row/drag-handle";

// The table's column and row handles and their menus, on Propel since the editor stage's phase 3,
// mounted against a real editor holding a table. What upstream v1.5.0 gives them, held here: a
// labelled handle button that announces its popup, menu rows that are buttons, labelled colour
// swatches in a labelled group, and a key closing the open menu.

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

// The utility extension's dropbar bookkeeping, which the menus call on open and close.
const DropbarStub = Extension.create({
  name: "utility",
  addStorage() {
    return { isTouchDevice: false };
  },
  addCommands() {
    return {
      addActiveDropbarExtension: () => () => true,
      removeActiveDropbarExtension: () => () => true,
    } as never;
  },
});

const TABLE =
  "<table><tbody>" +
  "<tr><th><p>Name</p></th><th><p>Owner</p></th></tr>" +
  "<tr><td><p>a</p></td><td><p>b</p></td></tr>" +
  "</tbody></table>";

let root: Root | undefined;
let host: HTMLElement | undefined;
let editor: Editor | undefined;

const mountHandle = async (kind: "column" | "row") => {
  editor = new Editor({
    extensions: [StarterKit, DropbarStub, Table, TableRow, TableHeader, TableCell],
    content: TABLE,
  });
  // The handles act on the table the selection is in: the first cell's text.
  editor.commands.setTextSelection(4);
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  const element =
    kind === "column"
      ? createElement(ColumnDragHandle, { editor, col: 0 })
      : createElement(RowDragHandle, { editor, row: 0 });
  await act(async () => root?.render(element));
  return host.querySelector("button")!;
};

const click = async (target: Element) => {
  await act(async () => {
    target.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
  });
};

const press = async (key: string) => {
  await act(async () => {
    document.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true }));
  });
};

const menuButton = (name: string) =>
  [...document.querySelectorAll<HTMLButtonElement>("[role='dialog'] button")].find(
    (candidate) => candidate.getAttribute("aria-label") === name || candidate.textContent?.trim() === name
  );

const columnCount = () => editor!.state.doc.firstChild!.firstChild!.childCount;
const rowCount = () => editor!.state.doc.firstChild!.childCount;

afterEach(async () => {
  await act(async () => root?.unmount());
  editor?.destroy();
  host?.remove();
  document.body.innerHTML = "";
  root = undefined;
  host = undefined;
  editor = undefined;
});

describe.each([
  ["column", "Column options", "Header column", ["Insert left", "Insert right"]],
  ["row", "Row options", "Header row", ["Insert above", "Insert below"]],
] as const)("the table %s handle", (kind, handleName, headerToggle, inserts) => {
  it("is a labelled button that announces its popup", async () => {
    const handle = await mountHandle(kind);
    expect(handle.getAttribute("type")).toBe("button");
    expect(handle.getAttribute("aria-label")).toBe(handleName);
    expect(handle.getAttribute("aria-haspopup")).toBe("dialog");
    expect(handle.getAttribute("aria-expanded")).toBe("false");
    // The focus ring Propel's handle gains; the 1.4 handle had none.
    expect(handle.className).toContain("focus-visible:ring-2");
  });

  it("opens a menu of buttons, and a key closes it", async () => {
    const handle = await mountHandle(kind);
    await click(handle);
    expect(handle.getAttribute("aria-expanded")).toBe("true");
    const dialog = document.querySelector("[role='dialog']");
    expect(dialog).not.toBeNull();
    expect(handle.getAttribute("aria-controls")).toBe(dialog!.id);

    for (const name of [headerToggle, ...inserts, "Duplicate", "Clear contents", "Delete"]) {
      const item = menuButton(name);
      expect(item, name).toBeDefined();
      expect(item!.getAttribute("type")).toBe("button");
      expect(item!.tabIndex).not.toBe(-1);
    }

    await press("Escape");
    expect(handle.getAttribute("aria-expanded")).toBe("false");
    expect(document.querySelector("[role='dialog']")).toBeNull();
  });

  it("labels the colour swatches inside an open, labelled group", async () => {
    const handle = await mountHandle(kind);
    await click(handle);

    const colour = menuButton("Color");
    expect(colour?.getAttribute("aria-expanded")).toBe("true");
    const group = document.querySelector("[role='group'][aria-label='Background colors']");
    expect(group).not.toBeNull();
    const swatches = [...group!.querySelectorAll("button")];
    expect(swatches.length).toBeGreaterThan(1);
    for (const swatch of swatches) {
      expect(swatch.getAttribute("type")).toBe("button");
      expect(swatch.getAttribute("aria-label")).toMatch(/ background color$/);
    }
    expect(swatches.at(-1)!.getAttribute("aria-label")).toBe("Clear background color");
  });

  it("runs an item and closes", async () => {
    const handle = await mountHandle(kind);
    const before = kind === "column" ? columnCount() : rowCount();
    await click(handle);
    await click(menuButton(inserts[1])!);
    expect(kind === "column" ? columnCount() : rowCount()).toBe(before + 1);
    expect(document.querySelector("[role='dialog']")).toBeNull();
  });
});
