/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { getSchema } from "@tiptap/core";
import { generateJSON } from "@tiptap/html";
import { describe, expect, it } from "vitest";

import { CoreEditorExtensionsWithoutProps } from "../src/core/extensions/core-without-props";
import { isDangerousHref, isNavigableHref } from "../src/core/extensions/custom-link/url-security";

/**
 * Malicious markup through the paths pasted or stored HTML takes into the
 * editor (FORK.md, "Security invariants", S18). Whatever survives the schema is
 * what the editor renders, so nothing executable may be left in it.
 */
const schema = getSchema(CoreEditorExtensionsWithoutProps);
const throughSchema = (html: string) =>
  JSON.stringify(schema.nodeFromJSON(generateJSON(html, CoreEditorExtensionsWithoutProps)).toJSON());

const PAYLOADS = [
  '<p>a<img src="x" onerror="alert(1)">b</p>',
  '<p onclick="alert(1)" onmouseover="alert(1)">text</p>',
  "<script>alert(1)</script><p>after</p>",
  '<p><a href="javascript:alert(1)">link</a></p>',
  '<p><a href="JaVaScRiPt:alert(1)">link</a></p>',
  '<p><a href="java&#x09;script:alert(1)">link</a></p>',
  '<p><a href="data:text/html,<script>alert(1)</script>">link</a></p>',
  '<p><a href="data:image/svg+xml,<svg onload=alert(1)>">link</a></p>',
  '<p><a href="vbscript:msgbox(1)">link</a></p>',
  '<iframe srcdoc="<script>alert(1)</script>"></iframe><p>after</p>',
  "<svg><script>alert(1)</script></svg><p>after</p>",
  '<p><span style="background:url(javascript:alert(1))">x</span></p>',
  '<object data="javascript:alert(1)"></object><p>after</p>',
  '<form action="javascript:alert(1)"><button>go</button></form>',
];

describe("malicious HTML through the editor schema", () => {
  it.each(PAYLOADS)("leaves nothing executable from %j", (payload) => {
    const json = throughSchema(payload).toLowerCase();
    expect(json).not.toMatch(/javascript:|vbscript:|data:text\/html|data:image\/svg/);
    expect(json).not.toMatch(/"on[a-z]+"/);
    expect(json).not.toMatch(/<script|srcdoc|"script"|"iframe"|"object"|"form"/);
  });
});

describe("obfuscated link schemes", () => {
  it.each([
    "javascript:alert(1)",
    " javascript:alert(1)",
    "\njava\nscript:alert(1)",
    "\u001fjavascript:alert(1)",
    "data:image/svg+xml,<svg onload=alert(1)>",
    "DATA:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==",
  ])("blocks %j and never opens it", (href) => {
    expect(isDangerousHref(href)).toBe(true);
    expect(isNavigableHref(href)).toBe(false);
  });

  it.each(["file:///etc/passwd", "blob:https://example.com/1", "about:blank", "chrome://settings"])(
    "does not open %j, which is not on the allow-list",
    (href) => {
      expect(isNavigableHref(href)).toBe(false);
    }
  );
});
