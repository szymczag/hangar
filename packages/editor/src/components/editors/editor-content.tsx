/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { EditorContent } from "@tiptap/react";
import type { Editor } from "@tiptap/react";
import type { ReactNode } from "react";

type Props = {
  className?: string;
  children?: ReactNode;
  editor: Editor | null;
  id: string;
  tabIndex?: number;
};

export function EditorContentWrapper(props: Props) {
  const { editor, className, children, tabIndex, id } = props;

  return (
    <div
      tabIndex={tabIndex}
      onFocus={(event) => {
        // Forward focus only when this wrapper itself takes it (it is tabbable through
        // `tabIndex`). React bubbles focus through the component tree, so a focus inside
        // a node view (the image toolbar) or inside a node view's portal (the full-screen
        // image viewer) reaches this handler too; forwarding those pulled focus straight
        // back into the editor on the next frame.
        if (event.target !== event.currentTarget) return;
        editor?.chain().focus(undefined, { scrollIntoView: false }).run();
      }}
      className={className}
    >
      <EditorContent editor={editor} id={id} />
      {children}
    </div>
  );
}
