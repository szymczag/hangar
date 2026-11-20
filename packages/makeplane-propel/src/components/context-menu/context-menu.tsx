import { ContextMenu as BaseContextMenu } from "@base-ui/react/context-menu";
import type * as React from "react";

type BaseContextMenuRootProps = BaseContextMenu.Root.Props;

export type ContextMenuProps = Omit<
  BaseContextMenuRootProps,
  "className" | "style" | "open" | "defaultOpen" | "onOpenChange" | "children"
> & {
  /** Whether the menu is open. Controlled; pair with `onOpenChange`. */
  open?: boolean;
  /** Whether the menu is open on mount. Uncontrolled. @default false */
  defaultOpen?: boolean;
  /** Called with the next open state when the menu opens or closes. */
  onOpenChange?: BaseContextMenuRootProps["onOpenChange"];
  /** The trigger and menu surface (`ContextMenuTrigger`, `ContextMenuContent`). */
  children?: React.ReactNode;
};

/**
 * Root of the context menu: holds the open state and the pointer position the menu anchors to, and
 * renders no element of its own. Wrap a `ContextMenuTrigger` and a `ContextMenuContent` in it; the
 * menu opens on right click or long press anywhere inside the trigger.
 */
export function ContextMenu(props: ContextMenuProps) {
  return <BaseContextMenu.Root {...props} />;
}
