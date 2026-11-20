import { Combobox as BaseCombobox } from "@base-ui/react/combobox";
import type * as React from "react";

import {
  type ComboboxSize,
  type ComboboxVariant,
  ComboboxInput as ComboboxInputElement,
  ComboboxInputGroup as ComboboxInputGroupElement,
  ComboboxInputGroupClear,
} from "../../elements/combobox";
import { ChevronDownOutline } from "../../icons";
import { Icon } from "../../internal/icon";

export type { ComboboxSize, ComboboxVariant };

export type ComboboxInputGroupProps = Omit<
  BaseCombobox.Input.Props,
  "className" | "style" | "render" | "size"
> & {
  /**
   * Frame look. `secondary` is the bordered field surface; `ghost` is borderless.
   *
   * @default "secondary"
   */
  variant?: ComboboxVariant;
  /** Visual size of the input row: height, text, and glyph sizing. Required. */
  size: ComboboxSize;
  /** Input placeholder. */
  placeholder?: string;
  /**
   * Decorative leading element at the inline-start, e.g. `<Icon icon={Search} tint="placeholder"
   * />`.
   */
  icon?: React.ReactNode;
  /**
   * The clear control (e.g. an `IconButton`), grafted onto Base UI's `Clear` behavior. It carries
   * its own — localizable — `aria-label`; the group bakes no label or glyph.
   */
  clear?: React.ReactElement;
  /**
   * The popup-trigger control (e.g. an `IconButton`), grafted onto Base UI's `Trigger` behavior. It
   * carries its own — localizable — `aria-label`; the group bakes no label or glyph. Omit it to
   * show a decorative chevron (the Figma end node) — the input still opens the list.
   */
  trigger?: React.ReactElement;
};

/**
 * The ready-made single-select input frame: grafts Base UI's `InputGroup` onto the styled frame and
 * Base UI's `Input` onto the styled text field, laying out an optional leading `icon` slot and the
 * consumer-provided `clear`/`trigger` controls. `clear` stays `keepMounted` in a reserved slot so
 * the trailing trigger does not shift when the value is empty. When `trigger` is omitted, a
 * decorative chevron is shown. All remaining props pass through to the input (the element that
 * carries the combobox behavior and accessible name).
 */
export function ComboboxInputGroup({
  size,
  variant,
  icon,
  clear,
  trigger,
  ...props
}: ComboboxInputGroupProps) {
  return (
    <BaseCombobox.InputGroup render={<ComboboxInputGroupElement size={size} variant={variant} />}>
      {icon}
      <BaseCombobox.Input {...props} render={<ComboboxInputElement />} />
      {clear != null ? (
        <ComboboxInputGroupClear>
          <BaseCombobox.Clear render={clear} keepMounted />
        </ComboboxInputGroupClear>
      ) : null}
      {trigger != null ? (
        <BaseCombobox.Trigger render={trigger} />
      ) : (
        <Icon tint="secondary">
          <ChevronDownOutline aria-hidden />
        </Icon>
      )}
    </BaseCombobox.InputGroup>
  );
}
