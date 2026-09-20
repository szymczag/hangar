/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import { parseInertHTML } from "./inert-html";

describe("parseInertHTML", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("parses with DOMParser as an HTML document and returns it", () => {
    const parsed = { body: {} };
    const parseFromString = vi.fn(() => parsed);
    vi.stubGlobal(
      "DOMParser",
      class {
        parseFromString = parseFromString;
      }
    );

    expect(parseInertHTML("<img src=x onerror=alert(1)>")).toBe(parsed);
    expect(parseFromString).toHaveBeenCalledWith("<img src=x onerror=alert(1)>", "text/html");
  });
});
