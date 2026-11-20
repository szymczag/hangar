import { Menu as BaseMenu } from "@base-ui/react/menu";
import type * as React from "react";

import {
  MenuItemContent,
  MenuItemTitle,
  MenuItemTitleRow,
  MenuItemTrailing,
  MenuLinkItem as MenuLinkItemElement,
  type MenuItemVariant,
} from "../../elements/menu";
import { resolveExternalLinkProps } from "../../internal/external-link";

export type MenuLinkItemProps = Omit<
  BaseMenu.LinkItem.Props,
  "children" | "className" | "label" | "style" | "render"
> & {
  /**
   * Row look. `neutral` is the standard text hierarchy, `accent` marks the primary action, and
   * `danger` marks a destructive one.
   *
   * @default "neutral"
   */
  variant?: MenuItemVariant;
  /** Leading element before the label, e.g. `<Icon icon={ExternalLink} tint="secondary" />`. */
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
 * The ready-made navigational `<a>` menu row: grafts Base UI's `Menu.LinkItem` behavior onto the
 * styled `MenuLinkItem` and lays out an optional leading icon, label, and end content.
 */
export function MenuLinkItem({
  variant,
  icon,
  label,
  trailing,
  external = false,
  ...props
}: MenuLinkItemProps) {
  const { target, rel, end } = resolveExternalLinkProps({
    external,
    target: props.target,
    rel: props.rel,
    trailing,
  });

  return (
    <BaseMenu.LinkItem
      {...props}
      target={target}
      rel={rel}
      render={<MenuLinkItemElement variant={variant} />}
    >
      {icon}
      <MenuItemContent>
        <MenuItemTitleRow>
          <MenuItemTitle>{label}</MenuItemTitle>
        </MenuItemTitleRow>
      </MenuItemContent>
      {end != null ? <MenuItemTrailing>{end}</MenuItemTrailing> : null}
    </BaseMenu.LinkItem>
  );
}
