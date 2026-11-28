/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Extension } from "@tiptap/core";
import { Plugin } from "@tiptap/pm/state";
import { Editor } from "@tiptap/react";
import { StarterKit } from "@tiptap/starter-kit";
import { act, createElement } from "react";
import { createRoot } from "react-dom/client";
import type { Root } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";
import { EditorContentWrapper } from "@/components/editors/editor-content";
import { CustomImageExtension } from "@/extensions/custom-image/extension";
import type { TFileHandler } from "@/types";

// The full-screen image viewer, mounted from a real image node view inside the editor's
// content wrapper, the way pages and work item descriptions render it. The 0.7.0-rc.1
// viewer never kept focus: the wrapper's focus handler, reached through React's
// component tree, pulled focus back into the editor, so Escape did nothing and `+`/`-`
// replaced the node-selected image.

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const IMAGE_SRC = "https://assets.example.test/image.png";

const fileHandler = {
  assetsUploadStatus: {},
  cancel: () => {},
  checkIfAssetExists: async () => true,
  delete: async () => {},
  getAssetDownloadSrc: async () => IMAGE_SRC,
  getAssetSrc: async () => IMAGE_SRC,
  restore: async () => {},
  upload: async () => "asset",
  duplicate: async () => "asset",
  validation: { maxFileSize: 5 * 1024 * 1024 },
} as unknown as TFileHandler;

// The utility extension's storage, which the image node view reads.
const UtilityStub = Extension.create({
  name: "utility",
  addStorage() {
    return { isTouchDevice: false, assetsUploadStatus: {} };
  },
});

// Stands in for the browser's typing path: a printable key that reaches the editor
// replaces the selection with that character, as it does with a node-selected image.
const TypingStub = Extension.create({
  name: "typingStub",
  addProseMirrorPlugins() {
    return [
      new Plugin({
        props: {
          handleKeyDown: (view, event) => {
            if (event.key.length !== 1) return false;
            view.dispatch(view.state.tr.insertText(event.key));
            return true;
          },
        },
      }),
    ];
  },
});

const CONTENT = {
  type: "doc",
  content: [
    { type: "paragraph", content: [{ type: "text", text: "before" }] },
    {
      type: "imageComponent",
      attrs: {
        id: "11111111-1111-4111-8111-111111111111",
        src: "asset-1",
        width: "300px",
        height: "150px",
        aspectRatio: 2,
        status: "uploaded",
      },
    },
    { type: "paragraph", content: [{ type: "text", text: "after" }] },
  ],
};

let root: Root | undefined;
let editor: Editor | undefined;

const nextFrames = async () => {
  // Focus moves on animation frames (the focus manager and the editor's focus command).
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 60));
  });
};

const imageCount = () => {
  let count = 0;
  editor!.state.doc.descendants((node) => {
    if (node.type.name === "imageComponent") count++;
  });
  return count;
};

const viewer = () => document.querySelector<HTMLElement>("[role='dialog'][aria-label='Fullscreen image viewer']");
const viewerButton = (name: string) => viewer()!.querySelector<HTMLButtonElement>(`button[aria-label='${name}']`)!;
const zoomLabel = () => viewer()!.querySelector(".tabular-nums")!.textContent;

const press = async (key: string, target: EventTarget = document.activeElement ?? document.body) => {
  await act(async () => {
    target.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true }));
  });
};

const mount = async () => {
  const portal = document.createElement("div");
  portal.id = "editor-portal";
  const host = document.createElement("div");
  document.body.append(host, portal);

  const mounted = new Editor({
    extensions: [StarterKit, UtilityStub, TypingStub, CustomImageExtension({ fileHandler, isEditable: true })],
    content: CONTENT,
  });
  editor = mounted;
  root = createRoot(host);
  await act(async () => {
    root?.render(
      createElement(
        "div",
        { className: "editor-container" },
        createElement(EditorContentWrapper, { editor: mounted, id: "description" })
      )
    );
  });
  await nextFrames();

  // The toolbar shows once the image has loaded and taken its initial size.
  const img = host.querySelector<HTMLImageElement>("img.image-component")!;
  Object.defineProperty(img, "naturalWidth", { value: 400 });
  Object.defineProperty(img, "naturalHeight", { value: 200 });
  await act(async () => {
    img.dispatchEvent(new Event("load"));
  });
  await nextFrames();

  // The image is node-selected, as it is after a click on it.
  mounted.commands.setNodeSelection(mounted.state.doc.firstChild!.nodeSize);
  mounted.view.focus();

  const opener = host.querySelector<HTMLButtonElement>("button[aria-label='View image in full screen']");
  expect(opener).not.toBeNull();
  return opener!;
};

const openWithClick = async (opener: HTMLButtonElement) => {
  await act(async () => {
    opener.focus();
    opener.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
  });
  await nextFrames();
};

afterEach(async () => {
  await act(async () => root?.unmount());
  editor?.destroy();
  document.body.innerHTML = "";
  root = undefined;
  editor = undefined;
});

describe("the full-screen image viewer", () => {
  it("moves focus inside the viewer when it opens, and keeps it there", async () => {
    const opener = await mount();
    await openWithClick(opener);

    expect(viewer()).not.toBeNull();
    expect(document.activeElement).toBe(viewerButton("Close image viewer"));

    // Pressing one of its own buttons keeps focus in the viewer.
    const zoomIn = viewerButton("Zoom in");
    await act(async () => {
      zoomIn.focus();
      zoomIn.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });
    await nextFrames();
    expect(viewer()!.contains(document.activeElement)).toBe(true);
    expect(document.activeElement).not.toBe(editor!.view.dom);
  });

  it("closes on Escape and returns focus to the full-screen button", async () => {
    const opener = await mount();
    await openWithClick(opener);

    await press("Escape");
    await nextFrames();

    expect(viewer()).toBeNull();
    expect(document.activeElement).toBe(opener);
    expect(imageCount()).toBe(1);
  });

  it("zooms with + and -, resets with 0, and never lets the keys reach the editor", async () => {
    const opener = await mount();
    await openWithClick(opener);
    expect(zoomLabel()).toBe("100%");

    await press("+");
    expect(zoomLabel()).toBe("150%");
    await press("=");
    expect(zoomLabel()).toBe("200%");
    // At the limit the zoom-in button stays focusable, so focus does not fall out.
    expect(viewerButton("Zoom in").getAttribute("aria-disabled")).toBe("true");
    await press("-");
    await press("-");
    await press("-");
    expect(zoomLabel()).toBe("50%");
    await press("0");
    expect(zoomLabel()).toBe("100%");

    // Even a key aimed straight at the editor is claimed while the viewer is open.
    await press("+", editor!.view.dom);
    expect(zoomLabel()).toBe("150%");

    expect(imageCount()).toBe(1);
    expect(viewer()).not.toBeNull();
  });

  it.each([
    ["Enter", "Enter"],
    ["Space", " "],
  ])("opens with %s on the focused full-screen button", async (_name, key) => {
    const opener = await mount();
    await act(async () => opener.focus());
    await nextFrames();
    // Focusing a button inside the editor no longer sends focus back to the editor.
    expect(document.activeElement).toBe(opener);

    await press(key);
    await nextFrames();

    expect(viewer()).not.toBeNull();
    expect(document.activeElement).toBe(viewerButton("Close image viewer"));
    expect(imageCount()).toBe(1);
  });
});
