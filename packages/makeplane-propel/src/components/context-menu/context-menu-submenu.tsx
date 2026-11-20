import { ContextMenu as BaseContextMenu } from "@base-ui/react/context-menu";
import type * as React from "react";

type BaseSubmenuRootProps = BaseContextMenu.SubmenuRoot.Props;

export type ContextMenuSubmenuProps = Omit<
  BaseSubmenuRootProps,
  "className" | "style" | "open" | "defaultOpen" | "onOpenChange" | "children"
> & {
  /** Whether the submenu is open. Controlled; pair with `onOpenChange`. */
  open?: boolean;
  /** Whether the submenu is open on mount. Uncontrolled. @default false */
  defaultOpen?: boolean;
  /** Called with the next open state when the submenu opens or closes. */
  onOpenChange?: BaseSubmenuRootProps["onOpenChange"];
  /** The submenu's trigger row and the `ContextMenuContent` it opens. */
  children?: React.ReactNode;
};

/**
 * Groups all parts of a nested submenu — its `ContextMenuSubmenuTrigger` row and the
 * `ContextMenuSubmenuContent` that opens beside it. Holds the submenu's own open state and renders
 * no element of its own.
 */
export function ContextMenuSubmenu(props: ContextMenuSubmenuProps) {
  return <BaseContextMenu.SubmenuRoot {...props} />;
}
