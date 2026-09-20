/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { inertHTML } from "@plane/csp/trusted-types";

/**
 * @description Parse an HTML string into a document with no browsing context:
 * nothing in it loads, runs or fires an event handler, whatever the string
 * contains. It is the one place our code turns an HTML string into DOM, so
 * that place can be reviewed on its own and, in phase 2 of
 * docs/trusted-types-plan.md, given the only Trusted Types policy our code
 * needs ("hangar-inert", see @plane/csp/trusted-types). Callers read from the
 * result or hand it to the editor schema; moving its nodes into the page would
 * undo what makes it safe.
 * @param {string} html
 * @returns {Document}
 */
export const parseInertHTML = (html: string): Document =>
  // TrustedHTML where the browser has Trusted Types, the string itself elsewhere;
  // TypeScript's DOM types only name the string.
  new DOMParser().parseFromString(inertHTML(html) as string, "text/html");
