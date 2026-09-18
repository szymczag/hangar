/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { Editor } from "@tiptap/core";
import { Plugin, PluginKey } from "@tiptap/pm/state";

/**
 * Markdown pasted from an application that also writes HTML to the clipboard.
 *
 * `tiptap-markdown` converts pasted markdown from a `clipboardTextParser`, and
 * ProseMirror only consults that parser when the clipboard carries no
 * `text/html`. Nearly every graphical application writes both flavours, so
 * pasting `# Heading` from a browser, Notion or VS Code left the `#` as a
 * literal character while the same text pasted from a terminal became a
 * heading. Chrome's "paste and match style" worked for the same reason: it
 * hands over the plain flavour alone.
 *
 * This plugin takes the plain flavour when the HTML one carries no formatting
 * of its own, which is the case for the wrappers those applications add around
 * plain lines. A paste that carries real markup is left to ProseMirror.
 */

const MARKDOWN_PATTERNS = [
  /^ {0,3}#{1,6}\s+\S/m, // heading
  /^ {0,3}(?:```|~~~)/m, // fenced code
  /^ {0,3}[-*+]\s+\S/m, // bullet list
  /^ {0,3}\d+[.)]\s+\S/m, // ordered list
  /^ {0,3}>\s+\S/m, // quote
  /^ {0,3}\|.*\|\s*$/m, // table row
  /^ {0,3}(?:[-*_]\s*){3,}$/m, // thematic break
  /^ {0,3}- \[[ xX]\]\s+/m, // task item
  /\*\*[^*\n]+\*\*/, // bold
  /(?<!\w)_[^_\n]+_(?!\w)/, // italic
  /`[^`\n]+`/, // inline code
  /~~[^~\n]+~~/, // strikethrough
  /\[[^\]\n]+\]\([^)\s]+\)/, // link or image
];

/** Whether this text carries markdown worth converting. */
export const looksLikeMarkdown = (text: string): boolean => {
  const trimmed = text.trim();
  // A single token is a word, a path or a URL far more often than markup.
  if (!trimmed || !/\s/.test(trimmed)) return false;
  return MARKDOWN_PATTERNS.some((pattern) => pattern.test(text));
};

/**
 * Tags a browser or plain editor adds when it wraps plain lines. Anything else
 * -- a heading, a list, a link, an emphasis mark -- is formatting the HTML
 * flavour carries and the markdown parser must not be given the chance to
 * reinvent.
 */
const PLAIN_WRAPPER_TAGS = new Set([
  "html",
  "head",
  "meta",
  "title",
  "style",
  "body",
  "div",
  "span",
  "p",
  "br",
  "font",
  "wbr",
]);

/** Whether the HTML flavour is only plain lines in wrappers. */
export const hasOnlyPlainWrappers = (tagNames: string[]): boolean =>
  tagNames.every((tag) => PLAIN_WRAPPER_TAGS.has(tag.toLowerCase()));

/**
 * Whether both flavours say the same characters.
 *
 * Whitespace is dropped rather than collapsed: `textContent` puts nothing
 * between block elements, so the HTML flavour of three `<div>`s reads back as
 * one run of words while the plain flavour has newlines. Comparing the
 * characters alone is what makes those two agree, and it is only ever reached
 * for HTML that passed the wrapper check above.
 */
export const htmlAddsNoFormatting = (htmlText: string, plainText: string): boolean =>
  htmlText.replace(/\s+/g, "") === plainText.replace(/\s+/g, "");

export const isPlainishHtml = (html: string, plainText: string): boolean => {
  if (!html.trim()) return true;

  // DOMParser, not `innerHTML` on a detached element. Assigning clipboard HTML
  // to `innerHTML` does not run <script>, but it does create elements that
  // fetch: `<img src=x onerror=...>` loads and fires its handler even when the
  // element was never inserted into the page, which would make inspecting the
  // paste the very thing that executes it. A document from DOMParser has no
  // browsing context, so nothing loads and no handler runs.
  const parsed = new DOMParser().parseFromString(html, "text/html");
  const tagNames = Array.from(parsed.body.querySelectorAll("*")).map((element) => element.tagName);
  if (!hasOnlyPlainWrappers(tagNames)) return false;
  return htmlAddsNoFormatting(parsed.body.textContent ?? "", plainText);
};

type Props = {
  editor: Editor;
};

export const MarkdownPastePlugin = (props: Props): Plugin => {
  const { editor } = props;

  return new Plugin({
    key: new PluginKey("markdown-paste"),
    props: {
      handlePaste: (view, event) => {
        if (!editor.isEditable || !event.clipboardData) return false;

        // The internal flavour is a copy from this editor, already exact.
        if (event.clipboardData.getData("text/plane-editor-html")) return false;

        const plainText = event.clipboardData.getData("text/plain");
        if (!plainText) return false;

        // A code block takes text verbatim; its own paste handler owns that.
        if (view.state.selection.$from.parent.type.name === "codeBlock") return false;

        const html = event.clipboardData.getData("text/html");
        if (!isPlainishHtml(html, plainText)) return false;
        if (!looksLikeMarkdown(plainText)) return false;

        const parsed = editor.storage.markdown?.parser?.parse(plainText);
        if (typeof parsed !== "string" || !parsed.trim()) return false;

        event.preventDefault();
        editor.commands.insertContent(parsed, { applyInputRules: false, applyPasteRules: false });
        return true;
      },
    },
  });
};
