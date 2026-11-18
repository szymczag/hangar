/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";

import { formatModifierShortcut, resolveShortcutKey } from "./shortcut-handler";
import type { TKeyboardLayoutMap } from "./shortcut-handler";

type TKeyInit = Partial<Pick<KeyboardEvent, "key" | "code" | "ctrlKey" | "metaKey" | "altKey" | "shiftKey">>;

const keyEvent = (init: TKeyInit): KeyboardEvent =>
  ({ key: "", code: "", ctrlKey: false, metaKey: false, altKey: false, shiftKey: false, ...init }) as KeyboardEvent;

describe("formatModifierShortcut", () => {
  // Copy work item URL and title are registered as cmd+shift+, and cmd+shift+'.
  // With Shift held the browser reports "<" and '"', which never matched.
  it("maps shifted punctuation back to its base key on a US layout", () => {
    expect(formatModifierShortcut(keyEvent({ key: "<", code: "Comma", ctrlKey: true, shiftKey: true }), null)).toBe(
      "cmd+shift+,"
    );
    expect(formatModifierShortcut(keyEvent({ key: '"', code: "Quote", metaKey: true, shiftKey: true }), null)).toBe(
      "cmd+shift+'"
    );
  });

  it("does not remap a glyph that sits on a different key in the active layout", () => {
    // UK layout: Shift+2 produces '"'. It must not fire the cmd+shift+' shortcut.
    expect(formatModifierShortcut(keyEvent({ key: '"', code: "Digit2", ctrlKey: true, shiftKey: true }), null)).toBe(
      'cmd+shift+"'
    );
  });

  it("uses the keyboard layout map when the browser provides one", () => {
    const layout: TKeyboardLayoutMap = new Map([["Comma", ","]]);
    expect(formatModifierShortcut(keyEvent({ key: ";", code: "Comma", ctrlKey: true, shiftKey: true }), layout)).toBe(
      "cmd+shift+,"
    );
  });
});

describe("resolveShortcutKey", () => {
  it("resolves letters by physical key on a non-Latin layout", () => {
    expect(resolveShortcutKey(keyEvent({ key: "и", code: "KeyB" }), null)).toBe("b");
  });

  it("names the space bar and lowercases named keys", () => {
    expect(resolveShortcutKey(keyEvent({ key: " ", code: "Space" }), null)).toBe("space");
    expect(resolveShortcutKey(keyEvent({ key: "Backspace", code: "Backspace" }), null)).toBe("backspace");
  });
});
