import type * as React from "react";

import { NewTabArrowOutline } from "../icons";
import { type ExternalAnchorProps, resolveExternalAnchorProps } from "./external-anchor";
import { rendersContent } from "./renders-content";

export type ExternalLinkProps = ExternalAnchorProps & {
  trailing: React.ReactNode;
};

/**
 * Resolves the three things a menu link-item's `external` flag sets together: `target="_blank"`,
 * `rel="noreferrer noopener"`, and a trailing arrow — shared by `MenuLinkItem` and
 * `ContextMenuLinkItem` so the `rel` security default lives in one place. The caller's own
 * `target`/ `rel` wins over `external`'s default; a supplied `trailing` wins over the arrow, since
 * it owns the end slot.
 */
export function resolveExternalLinkProps({ external, target, rel, trailing }: ExternalLinkProps): {
  target: React.ComponentPropsWithoutRef<"a">["target"];
  rel: React.ComponentPropsWithoutRef<"a">["rel"];
  end: React.ReactNode;
} {
  const anchorProps = resolveExternalAnchorProps({ external, target, rel });
  return {
    ...anchorProps,
    end: rendersContent(trailing) ? (
      trailing
    ) : external ? (
      <NewTabArrowOutline aria-hidden />
    ) : undefined,
  };
}
