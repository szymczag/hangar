/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { MarkType } from "@tiptap/pm/model";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import { isNavigableHref } from "../url-security";

type ClickHandlerOptions = {
  type: MarkType;
};

export function clickHandler(_options: ClickHandlerOptions): Plugin {
  return new Plugin({
    key: new PluginKey("handleClickLink"),
    props: {
      handleClick: (view, pos, event) => {
        if (event.button !== 0) {
          return false;
        }

        let a = event.target as HTMLElement;
        const els: HTMLElement[] = [];

        while (a?.nodeName !== "DIV") {
          els.push(a);
          a = a?.parentNode as HTMLElement;
        }

        // The anchor itself, not event.target: a click on bold or italic text
        // inside a link targets that child. Its `href` is the browser-resolved
        // URL; the raw mark attribute is never used, because a value that
        // arrived through a collaborative update never passed parseHTML.
        const anchor = els.find((value) => value?.nodeName === "A") as HTMLAnchorElement | undefined;
        if (!anchor) {
          return false;
        }

        // renderHTML blanks a dangerous href; `anchor.href` would resolve that
        // empty attribute to the current page, so check the attribute first.
        const href = anchor.getAttribute("href") ? anchor.href : "";
        if (href && isNavigableHref(href)) {
          // Always a new browsing context without an opener, so the opened
          // page cannot navigate this one (reverse tabnabbing).
          window.open(href, "_blank", "noopener,noreferrer");
          return true;
        }

        return false;
      },
    },
  });
}
