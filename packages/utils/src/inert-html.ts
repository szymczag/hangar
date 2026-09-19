/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * @description Parse an HTML string into a document with no browsing context:
 * nothing in it loads, runs or fires an event handler, whatever the string
 * contains. It is the one place our code turns an HTML string into DOM, so
 * that place can be reviewed on its own and, in phase 2 of
 * docs/trusted-types-plan.md, given the only Trusted Types policy our code
 * needs. Callers read from the result or hand it to the editor schema; moving
 * its nodes into the page would undo what makes it safe.
 * @param {string} html
 * @returns {Document}
 */
export const parseInertHTML = (html: string): Document => new DOMParser().parseFromString(html, "text/html");
