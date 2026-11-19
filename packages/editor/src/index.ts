/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// editors
export {
  CollaborativeDocumentEditorWithRef,
  DocumentEditorWithRef,
  LiteTextEditorWithRef,
  RichTextEditorWithRef,
} from "@/components/editors";

// constants
export * from "@/constants/common";

// helpers
export * from "@/helpers/common";
// The document codecs are not exported here: they import @tiptap/html, whose Node
// condition is its happy-dom server entry, and an SSR bundle of this entry would
// inline happy-dom. Import them from `@plane/editor/lib` (browser) or
// `@plane/editor/server` (Node).

export { CORE_EXTENSIONS } from "@/constants/extension";
export { ADDITIONAL_EXTENSIONS } from "@/constants/extensions";

// types
export * from "@/types";

// additional exports
export { TrailingNode } from "@/extensions/trailing-node";
