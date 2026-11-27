/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { Node as ProseMirrorNode } from "@tiptap/pm/model";
import type { EditorState, Selection } from "@tiptap/pm/state";
// plane imports
import { cn } from "@plane/utils";
// constants
import { CORE_EXTENSIONS } from "@/constants/extension";
// extensions
import { isAllowedLinkProtocol, isDangerousHref } from "@/extensions/custom-link/url-security";

type EditorClassNameArgs = {
  noBorder?: boolean;
  borderOnFocus?: boolean;
  containerClassName?: string;
};

export const getEditorClassNames = ({ noBorder, borderOnFocus, containerClassName }: EditorClassNameArgs) =>
  cn(
    "w-full max-w-full focus:border-0 focus:outline-none sm:rounded-lg",
    {
      "border border-subtle-1": !noBorder,
      "border-strong focus:border": borderOnFocus,
    },
    containerClassName
  );

// Helper function to find the parent node of a specific type
export const findParentNodeOfType = (
  selection: Selection,
  typeName: string[]
): {
  node: ProseMirrorNode;
  pos: number;
  depth: number;
} | null => {
  let depth = selection.$anchor.depth;
  while (depth > 0) {
    const node = selection.$anchor.node(depth);
    if (typeName.includes(node.type.name)) {
      return {
        node,
        pos: selection.$anchor.start(depth) - 1,
        depth,
      };
    }
    depth--;
  }
  return null;
};

export const findTableAncestor = (node: Node | null): HTMLTableElement | null => {
  while (node !== null && node.nodeName !== "TABLE") {
    node = node.parentNode;
  }
  return node as HTMLTableElement;
};

export const getTrimmedHTML = (html: string) =>
  html
    .replace(/^(?:<p><\/p>)+/g, "") // Remove from beginning
    .replace(/(?:<p><\/p>)+$/g, ""); // Remove from end

// `host:port` with no scheme (`localhost:3000`, `example.com:8080/a`). The URL
// parser reads the host as a scheme, so it is normalised like other scheme-less input.
const HOST_WITH_PORT = /^[a-z0-9.-]+:\d+(?:[/?#]|$)/i;

/**
 * Validates what a user typed into a link input (and what autolink proposes).
 * Only the link allowlist (`ALLOWED_LINK_PROTOCOLS`: http, https, mailto, tel)
 * is accepted; any other scheme is refused rather than saved, because a saved
 * link is one the browser opens on a middle-click, a modifier-click or in a
 * read-only view. Input with no scheme is normalised to `https://`.
 */
export const isValidHttpUrl = (string: string): { isValid: boolean; url: string } => {
  // The raw input first, as the link mark's renderer and the click handler read it: a scheme
  // hidden behind tabs, newlines or leading control characters is refused before URL parsing.
  if (isDangerousHref(string)) {
    return { isValid: false, url: string };
  }

  let parsed: URL | null = null;
  try {
    parsed = new URL(string);
  } catch {
    // Not an absolute URL - normalised with https below.
  }

  if (parsed) {
    if (isAllowedLinkProtocol(parsed.protocol)) {
      return { isValid: true, url: string };
    }
    // Any other scheme is refused, unless the "scheme" is a host with a port.
    if (!HOST_WITH_PORT.test(string)) {
      return { isValid: false, url: string };
    }
  }

  // Scheme-less input: try again with an https:// prefix.
  try {
    const urlWithHttps = `https://${string}`;
    // oxlint-disable-next-line no-new -- parsing is the validation
    new URL(urlWithHttps);
    return {
      isValid: true,
      url: urlWithHttps,
    };
  } catch {
    return {
      isValid: false,
      url: string,
    };
  }
};

export const getParagraphCount = (editorState: EditorState | undefined) => {
  if (!editorState) return 0;
  let paragraphCount = 0;
  editorState.doc.descendants((node) => {
    if (node.type.name === CORE_EXTENSIONS.PARAGRAPH && node.content.size > 0) paragraphCount++;
  });
  return paragraphCount;
};
