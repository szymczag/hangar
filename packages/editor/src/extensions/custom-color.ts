/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Mark, mergeAttributes } from "@tiptap/core";
// constants
import { CORE_EXTENSIONS } from "@/constants/extension";
// helpers
import { sanitizeColorKey } from "@/helpers/attribute-guards";

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    [CORE_EXTENSIONS.CUSTOM_COLOR]: {
      /**
       * Set the text color
       * @param {string} color The color to set
       * @example editor.commands.setTextColor('red')
       */
      setTextColor: (color: string) => ReturnType;

      /**
       * Unset the text color
       * @example editor.commands.unsetTextColor()
       */
      unsetTextColor: () => ReturnType;
      /**
       * Set the background color
       * @param {string} backgroundColor The color to set
       * @example editor.commands.setBackgroundColor('red')
       */
      setBackgroundColor: (backgroundColor: string) => ReturnType;

      /**
       * Unset the background color
       * @example editor.commands.unsetBackgroundColorColor()
       */
      unsetBackgroundColor: () => ReturnType;
    };
  }
}

export const CustomColorExtension = Mark.create({
  name: CORE_EXTENSIONS.CUSTOM_COLOR,

  addOptions() {
    return {
      HTMLAttributes: {},
    };
  },

  addAttributes() {
    // Palette keys only, rendered as data attributes and coloured by
    // editor.css. No inline style: an arbitrary value interpolated into
    // `style` was CSS injection, and inline style attributes are what a
    // strict Content-Security-Policy (style-src-attr 'none') refuses.
    return {
      color: {
        default: null,
        parseHTML: (element: HTMLElement) => sanitizeColorKey(element.getAttribute("data-text-color")),
        renderHTML: (attributes: { color: unknown }) => {
          const color = sanitizeColorKey(attributes.color);
          return color ? { "data-text-color": color } : {};
        },
      },
      backgroundColor: {
        default: null,
        parseHTML: (element: HTMLElement) => sanitizeColorKey(element.getAttribute("data-background-color")),
        renderHTML: (attributes: { backgroundColor: unknown }) => {
          const backgroundColor = sanitizeColorKey(attributes.backgroundColor);
          return backgroundColor ? { "data-background-color": backgroundColor } : {};
        },
      },
    };
  },

  addStorage() {
    return {
      markdown: {
        serialize: {
          open: "",
          close: "",
          mixable: true,
          expelEnclosingWhitespace: true,
        },
      },
    };
  },

  // @ts-expect-error types are incorrect
  // TODO: check this and update types
  parseHTML() {
    return [
      {
        tag: "span",
        getAttrs: (node) => node.getAttribute("data-text-color") && null,
      },
      {
        tag: "span",
        getAttrs: (node) => node.getAttribute("data-background-color") && null,
      },
    ];
  },

  renderHTML({ HTMLAttributes }) {
    return ["span", mergeAttributes(this.options.HTMLAttributes, HTMLAttributes), 0];
  },

  addCommands() {
    return {
      setTextColor:
        (color: string) =>
        ({ chain }) =>
          chain().setMark(this.name, { color }).run(),
      unsetTextColor:
        () =>
        ({ chain }) =>
          chain().setMark(this.name, { color: null }).run(),
      setBackgroundColor:
        (backgroundColor: string) =>
        ({ chain }) =>
          chain().setMark(this.name, { backgroundColor }).run(),
      unsetBackgroundColor:
        () =>
        ({ chain }) =>
          chain().setMark(this.name, { backgroundColor: null }).run(),
    };
  },
});
