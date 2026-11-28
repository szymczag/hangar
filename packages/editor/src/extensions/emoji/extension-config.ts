/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { shortcodeToEmoji } from "@tiptap/extension-emoji";
import type { Node as ProseMirrorNode } from "@tiptap/pm/model";
import type { MarkdownSerializerState } from "prosemirror-markdown";
// local imports
import { Emoji } from "./emoji";
import { EDITOR_EMOJIS } from "./emoji-data";

/**
 * The emoji node with its emoji data and markdown serializer, without the
 * suggestion renderer. The server codecs build their schema from this: the
 * renderer mounts the React suggestion list, which must not load in live.
 * The browser editor's `EmojiExtension` adds the renderer.
 */
export const EmojiExtensionConfig = Emoji.extend({
  addStorage() {
    const extensionOptions = this.options;

    return {
      ...this.parent!(),
      markdown: {
        serialize(state: MarkdownSerializerState, node: ProseMirrorNode) {
          const emojiItem = shortcodeToEmoji(node.attrs.name, extensionOptions.emojis);
          if (emojiItem?.emoji) {
            state.write(emojiItem?.emoji);
          } else {
            state.write(`:${node.attrs.name}:`);
          }
        },
      },
    };
  },
}).configure({
  emojis: EDITOR_EMOJIS,
  enableEmoticons: true,
});
