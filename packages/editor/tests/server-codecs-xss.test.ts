/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";

import { convertHTMLDocumentToAllFormats } from "../src/server";

/**
 * Live converts stored or submitted HTML with the server entry, which parses it
 * in happy-dom rather than a browser (FORK.md, "Security invariants", S18). The
 * schema must strip the same executable markup there, and parsing must never
 * run a script.
 */
const PAYLOADS = [
  '<p>a<img src="x" onerror="globalThis.__hangarXss = 1">b</p>',
  "<script>globalThis.__hangarXss = 1</script><p>after</p>",
  '<p><a href="javascript:alert(1)">link</a></p>',
  '<p><a href="java&#x09;script:alert(1)">link</a></p>',
  '<p><a href="data:text/html,<script>alert(1)</script>">link</a></p>',
  '<iframe srcdoc="<script>globalThis.__hangarXss = 1</script>"></iframe><p>after</p>',
  "<svg><script>globalThis.__hangarXss = 1</script></svg><p>after</p>",
  '<p onclick="alert(1)">text</p>',
];

const EXECUTABLE = /javascript:|data:text\/html|<script|srcdoc|<iframe|\son[a-z]+=/i;

describe("the server document codec", () => {
  it.each(["rich", "document"] as const)("leaves nothing executable in %s documents", (variant) => {
    for (const document_html of PAYLOADS) {
      const formats = convertHTMLDocumentToAllFormats({ document_html, variant });
      expect(formats.description_html).not.toMatch(EXECUTABLE);
      expect(JSON.stringify(formats.description_json)).not.toMatch(EXECUTABLE);
    }
    expect(Reflect.get(globalThis, "__hangarXss")).toBeUndefined();
  });
});
