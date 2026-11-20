import { ContextMenu as BaseContextMenu } from "@base-ui/react/context-menu";
import type * as React from "react";

import {
  ContextMenuItemLabel,
  ContextMenuItemTrailing,
  ContextMenuLinkItem as ContextMenuLinkItemElement,
  type ContextMenuItemVariant,
} from "../../elements/context-menu";
import { resolveExternalLinkProps } from "../../internal/external-link";

export type ContextMenuLinkItemProps = Omit<
  BaseContextMenu.LinkItem.Props,
  "children" | "className" | "label" | "style" | "render"
> & {
  /**
   * Row look. `neutral` is the standard text hierarchy and `danger` marks a destructive action.
   *
   * @default "neutral"
   */
  variant?: ContextMenuItemVariant;
  /** Leading element before the label, e.g. `<Icon icon={ExternalLink} />`. */
  icon?: React.ReactNode;
  /** Primary row label. */
  label: string;
  /** Content pinned at the row's inline end, e.g. `<Shortcut keys="⌘ K" />` or a count `<Badge />`. */
  trailing?: React.ReactNode;
  /**
   * The row leaves the app. Sets the three things a link out has to carry, together: a trailing
   * arrow so the row says where it goes, `target="_blank"`, and `rel="noreferrer noopener"`.
   *
   * They are one prop because they are one decision, and because two of them are easy to forget — a
   * missing `rel` is a security default, not a style nit. Both are overridable: pass your own
   * `target` or `rel` and it wins. Passing `trailing` also wins, in which case the row is yours to
   * annotate.
   *
   * @default false
   */
  external?: boolean;
};

/**
 * The ready-made navigational menu row: grafts Base UI's `LinkItem` behavior onto the styled
 * `ContextMenuLinkItem` and composes its region parts — a leading icon, the label, and optional
 * trailing content.
 */
export function ContextMenuLinkItem({
  variant,
  icon,
  trailing,
  label,
  external = false,
  ...props
}: ContextMenuLinkItemProps) {
  const { target, rel, end } = resolveExternalLinkProps({
    external,
    target: props.target,
    rel: props.rel,
    trailing,
  });

  return (
    <BaseContextMenu.LinkItem
      {...props}
      target={target}
      rel={rel}
      render={<ContextMenuLinkItemElement variant={variant} />}
    >
      {icon}
      <ContextMenuItemLabel>{label}</ContextMenuItemLabel>
      {end != null ? <ContextMenuItemTrailing>{end}</ContextMenuItemTrailing> : null}
    </BaseContextMenu.LinkItem>
  );
}
