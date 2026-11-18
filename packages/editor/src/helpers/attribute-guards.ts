/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// constants
import { COLORS_LIST } from "@/constants/common";
import { CORE_EXTENSIONS } from "@/constants/extension";

/**
 * Value guards for node and mark attributes.
 *
 * Attribute values reach the editor two ways: from HTML through `parseHTML`,
 * and from the collaborative document, where they never pass `parseHTML`. A
 * guard therefore has to run in both `parseHTML` and `renderHTML`; the schema
 * limits which attribute names exist, only these functions limit their values.
 * Every guard returns a value from a closed set, or null.
 */

export const EDITOR_COLOR_KEYS: ReadonlySet<string> = new Set(COLORS_LIST.map((color) => color.key));

// Stored table colours were written as the palette's CSS variable before they
// were stored as keys; both forms resolve to the same key.
const EDITOR_COLOR_VARIABLE = /^var\(--editor-colors-([a-z-]+)-(?:text|background)\)$/;

/** A palette key (`gray`, `light-blue`, ...) or null. */
export const sanitizeColorKey = (value: unknown): string | null => {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  if (EDITOR_COLOR_KEYS.has(trimmed)) return trimmed;
  const match = EDITOR_COLOR_VARIABLE.exec(trimmed);
  if (match && EDITOR_COLOR_KEYS.has(match[1])) return match[1];
  return null;
};

export const EDITOR_TEXT_ALIGNMENTS = ["left", "center", "right"] as const;
export type TEditorTextAlignment = (typeof EDITOR_TEXT_ALIGNMENTS)[number];

/** One of the supported alignments or null. */
export const sanitizeTextAlign = (value: unknown): TEditorTextAlignment | null =>
  typeof value === "string" && (EDITOR_TEXT_ALIGNMENTS as readonly string[]).includes(value.trim())
    ? (value.trim() as TEditorTextAlignment)
    : null;

type TAttributeGuard = (value: unknown) => unknown;

// Attributes whose values the renderers turn into CSS or URLs, per node or
// mark type. `undefined` removes the attribute so the schema default applies.
const DOCUMENT_ATTRIBUTE_GUARDS: Record<string, Record<string, TAttributeGuard>> = {
  [CORE_EXTENSIONS.PARAGRAPH]: { textAlign: sanitizeTextAlign },
  [CORE_EXTENSIONS.HEADING]: { textAlign: sanitizeTextAlign },
  [CORE_EXTENSIONS.TABLE_CELL]: { background: sanitizeColorKey, textColor: sanitizeColorKey },
  [CORE_EXTENSIONS.TABLE_HEADER]: { background: sanitizeColorKey },
  [CORE_EXTENSIONS.TABLE_ROW]: { background: sanitizeColorKey, textColor: sanitizeColorKey },
  [CORE_EXTENSIONS.CUSTOM_COLOR]: { color: sanitizeColorKey, backgroundColor: sanitizeColorKey },
  [CORE_EXTENSIONS.CUSTOM_LINK]: { target: () => undefined, rel: () => undefined, class: () => undefined },
};

type TDocumentJSON = {
  type?: string;
  attrs?: Record<string, unknown>;
  marks?: TDocumentJSON[];
  content?: TDocumentJSON[];
  [key: string]: unknown;
};

const guardAttributes = (item: TDocumentJSON): TDocumentJSON => {
  const guards = item.type ? DOCUMENT_ATTRIBUTE_GUARDS[item.type] : undefined;
  if (!guards || !item.attrs) return item;
  const attrs = { ...item.attrs };
  for (const [name, guard] of Object.entries(guards)) {
    if (!(name in attrs)) continue;
    const value = guard(attrs[name]);
    if (value === undefined) delete attrs[name];
    else attrs[name] = value;
  }
  return { ...item, attrs };
};

/**
 * Applies the render-time guards to stored document JSON, so the JSON kept
 * beside the HTML carries the same values the editor would render. The
 * collaborative document itself is left as it is: every renderer guards its
 * attributes, and rewriting a Yjs document outside the session would give it
 * a history the connected clients do not share.
 */
export const normalizeDocumentJSON = <T extends object>(document: T): T => {
  const walk = (item: TDocumentJSON): TDocumentJSON => {
    const guarded = guardAttributes(item);
    return {
      ...guarded,
      ...(guarded.marks ? { marks: guarded.marks.map(guardAttributes) } : {}),
      ...(guarded.content ? { content: guarded.content.map(walk) } : {}),
    };
  };
  return walk(document as TDocumentJSON) as T;
};
