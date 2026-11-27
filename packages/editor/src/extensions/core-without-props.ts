/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { TaskItem } from "@tiptap/extension-task-item";
import { TaskList } from "@tiptap/extension-task-list";
import { Underline } from "@tiptap/extension-underline";
// plane editor imports
import { CoreEditorAdditionalExtensionsWithoutProps } from "@/extensions/core/without-props";
// extensions
import { CustomCalloutExtensionConfig } from "./callout/extension-config";
import { CustomCodeBlockExtensionWithoutProps } from "./code/without-props";
import { CustomCodeInlineExtension } from "./code-inline";
import { CustomColorExtension } from "./custom-color";
import { CustomImageExtensionConfig } from "./custom-image/extension-config";
import { CustomLinkExtension } from "./custom-link";
import { EmojiExtensionConfig } from "./emoji/extension-config";
import { CustomHorizontalRule } from "./horizontal-rule";
import { ImageExtensionConfig } from "./image/extension-config";
import { CustomMentionExtensionConfig } from "./mentions/extension-config";
import { CustomQuoteExtension } from "./quote";
import { CustomStarterKitExtension } from "./starter-kit";
import { TableCell } from "./table/table-cell";
import { TableHeader } from "./table/table-header";
import { TableRow } from "./table/table-row";
import { TableExtensionConfig } from "./table/table/extension-config";
import { CustomTextAlignExtension } from "./text-align";
import { CustomTextStyle as TextStyle } from "./text-style";
import { WorkItemEmbedExtensionConfig } from "./work-item-embed/extension-config";

// The schema the server codecs in `@plane/editor/lib` and `@plane/editor/server`
// build. Live loads this graph in a production-only install, so nothing here may
// reach React views or UI packages (tests/lib-entry-ui-free.test.ts); each
// extension is the schema-only config its browser counterpart extends, and
// tests/schema-parity.test.ts holds the two schemas equal.
export const CoreEditorExtensionsWithoutProps = [
  CustomStarterKitExtension({
    enableHistory: true,
  }),
  EmojiExtensionConfig,
  CustomQuoteExtension,
  CustomHorizontalRule,
  CustomLinkExtension,
  ImageExtensionConfig,
  CustomImageExtensionConfig,
  Underline,
  TextStyle,
  TaskList.configure({
    HTMLAttributes: {
      class: "not-prose pl-2 space-y-2",
    },
  }),
  TaskItem.configure({
    HTMLAttributes: {
      class: "flex",
    },
    nested: true,
  }),
  CustomCodeInlineExtension,
  CustomCodeBlockExtensionWithoutProps,
  TableExtensionConfig,
  TableHeader,
  TableCell,
  TableRow,
  CustomMentionExtensionConfig,
  CustomTextAlignExtension,
  CustomCalloutExtensionConfig,
  CustomColorExtension,
  ...CoreEditorAdditionalExtensionsWithoutProps,
];

export const DocumentEditorExtensionsWithoutProps = [WorkItemEmbedExtensionConfig];
