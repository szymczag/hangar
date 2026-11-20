import { ContextMenu as BaseContextMenu } from "@base-ui/react/context-menu";
import type * as React from "react";

import {
  ContextMenuItemLabel,
  type ContextMenuItemVariant,
  ContextMenuRadioItem as ContextMenuRadioItemElement,
  ContextMenuRadioItemCheck,
  ContextMenuRadioItemIndicator,
} from "../../elements/context-menu";
import { TickOutline } from "../../icons";
import { useMenuRadioMarker } from "../../internal/menu-radio-marker";
import { RadioDot } from "../../internal/radio-dot";

export type ContextMenuRadioItemProps = Omit<
  BaseContextMenu.RadioItem.Props,
  "children" | "className" | "label" | "style" | "render"
> & {
  /**
   * Row look. `neutral` is the standard text hierarchy and `danger` marks a destructive action.
   *
   * @default "neutral"
   */
  variant?: ContextMenuItemVariant;
  /**
   * Leading element, e.g. `<Icon icon={AlignLeft} />`. With the group's `marker="radio"` it sits
   * after the ring; with the default tick it leads the row.
   */
  icon?: React.ReactNode;
  /** Primary row label. */
  label: string;
  /** Content pinned at the row's inline end, e.g. `<Shortcut keys="⌘ K" />` or a count `<Badge />`. */
  trailing?: React.ReactNode;
};

/**
 * The ready-made single-select context-menu row: grafts Base UI's `RadioItem` behavior onto the
 * styled row and marks the current row the way its `ContextMenuRadioGroup`'s `marker` says. `check`
 * (the default): a kept-mounted trailing tick on the selected row. `radio`: a leading ring drawn on
 * every row with only its inner dot hiding, for a popup that also holds a checkbox group. Wrap rows
 * in a `ContextMenuRadioGroup` carrying `value`/`onValueChange`; both the selected state and the
 * marker come from context.
 */
export function ContextMenuRadioItem({
  variant,
  icon,
  trailing,
  label,
  ...props
}: ContextMenuRadioItemProps) {
  const marker = useMenuRadioMarker();

  return (
    <BaseContextMenu.RadioItem
      {...props}
      render={<ContextMenuRadioItemElement variant={variant} />}
    >
      {marker === "radio" ? (
        <BaseContextMenu.RadioItemIndicator keepMounted render={<ContextMenuRadioItemIndicator />}>
          <RadioDot aria-hidden />
        </BaseContextMenu.RadioItemIndicator>
      ) : null}
      {icon}
      <ContextMenuItemLabel>{label}</ContextMenuItemLabel>
      {marker === "check" ? (
        <BaseContextMenu.RadioItemIndicator keepMounted render={<ContextMenuRadioItemCheck />}>
          <TickOutline aria-hidden />
        </BaseContextMenu.RadioItemIndicator>
      ) : null}
      {trailing}
    </BaseContextMenu.RadioItem>
  );
}
