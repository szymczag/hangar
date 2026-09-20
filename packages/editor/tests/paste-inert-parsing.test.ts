/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

/**
 * Guards the rule that pasted HTML is parsed where nothing can run.
 *
 * Asserted against the source rather than against behaviour because the hazard
 * needs a browsing context to demonstrate, and this package's tests run in node
 * with no DOM. What can be checked here is the property that actually matters:
 * that untrusted markup never reaches `innerHTML`.
 *
 * The distinction these helpers got wrong is subtle enough to be worth writing
 * down. Assigning clipboard HTML to `innerHTML` does not execute `<script>`,
 * which is what makes it look safe, and the element is never inserted into the
 * page, which makes it look safer still. Neither matters: constructing
 * `<img src=x onerror=…>` attempts the load and fires the handler regardless.
 * Inspecting the paste becomes the thing that executes it.
 *
 * Either the parse itself or `parseInertHTML` counts: that helper is the one
 * `DOMParser` call of ours, made through the "hangar-inert" Trusted Types
 * policy (docs/trusted-types-plan.md), and going through it is what keeps the
 * parse allowed where Trusted Types are enforced.
 */
const here = path.dirname(fileURLToPath(import.meta.url));

const UNTRUSTED_HTML_HELPERS = [
  // Reads the `text/plane-editor-html` clipboard flavour, which any page can
  // set on a copy event.
  path.join(here, "../src/core/helpers/paste-asset.ts"),
  // Exported from the utils barrel, so its input cannot be assumed trusted.
  path.join(here, "../../utils/src/editor/common.ts"),
];

/** `x.innerHTML = …`, ignoring reads such as `nodesArray.push(div.innerHTML)`. */
const ASSIGNS_INNER_HTML = /\.innerHTML\s*=(?!=)/;

/** The inert parse, directly or through the helper that owns it. */
const PARSES_INERTLY = /DOMParser|parseInertHTML/;

describe("helpers that handle untrusted HTML", () => {
  it.each(UNTRUSTED_HTML_HELPERS)("parses inertly instead of assigning innerHTML: %s", (file) => {
    const source = readFileSync(file, "utf8");
    const code = source
      .split("\n")
      .filter((line) => !line.trim().startsWith("*") && !line.trim().startsWith("//"))
      .join("\n");

    expect(ASSIGNS_INNER_HTML.test(code)).toBe(false);
    expect(PARSES_INERTLY.test(code)).toBe(true);
  });
});
