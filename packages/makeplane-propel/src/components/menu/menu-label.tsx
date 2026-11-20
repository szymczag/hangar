import { Menu as BaseMenu } from "@base-ui/react/menu";
import type * as React from "react";

import { MenuLabel as MenuLabelElement, MenuLabelMeta, MenuLabelTitle } from "../../elements/menu";

export type MenuLabelProps = Omit<BaseMenu.GroupLabel.Props, "className" | "style" | "render"> & {
  /** Content pinned at the heading row's inline end, e.g. a count or a "Clear" action. */
  meta?: React.ReactNode;
  /** The heading text. */
  children?: React.ReactNode;
};

/**
 * A non-interactive section heading for a group of menu items: grafts Base UI's `Menu.GroupLabel`
 * behavior onto the styled `MenuLabel`. Place it inside the `MenuGroup` it names, so Base UI wires
 * it as that group's accessible label.
 */
export function MenuLabel({ meta, children, ...props }: MenuLabelProps) {
  return (
    <BaseMenu.GroupLabel {...props} render={<MenuLabelElement />}>
      <MenuLabelTitle>{children}</MenuLabelTitle>
      {meta != null ? <MenuLabelMeta>{meta}</MenuLabelMeta> : null}
    </BaseMenu.GroupLabel>
  );
}
