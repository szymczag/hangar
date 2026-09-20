/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { TextAlign } from "@tiptap/extension-text-align";
// helpers
import { EDITOR_TEXT_ALIGNMENTS, sanitizeTextAlign } from "@/helpers/attribute-guards";

export type TTextAlign = "left" | "center" | "right";

// Rendered as `data-text-align` and aligned by editor.css, not as an inline
// `style="text-align: …"`: inline style attributes are what a strict
// Content-Security-Policy (style-src-attr 'none') refuses. The value is
// checked on render as well as on parse, because a value from the
// collaborative document never passes parseHTML.
export const CustomTextAlignExtension = TextAlign.extend({
  addGlobalAttributes() {
    return [
      {
        types: this.options.types,
        attributes: {
          textAlign: {
            default: null,
            parseHTML: (element: HTMLElement) =>
              // Content saved before this change carries the inline style.
              sanitizeTextAlign(element.getAttribute("data-text-align")) ?? sanitizeTextAlign(element.style?.textAlign),
            renderHTML: (attributes: { textAlign?: unknown }) => {
              const textAlign = sanitizeTextAlign(attributes.textAlign);
              return textAlign ? { "data-text-align": textAlign } : {};
            },
          },
        },
      },
    ];
  },
}).configure({
  alignments: [...EDITOR_TEXT_ALIGNMENTS],
  types: ["heading", "paragraph"],
});
