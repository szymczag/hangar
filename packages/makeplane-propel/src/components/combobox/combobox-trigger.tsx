import { Combobox as BaseCombobox } from "@base-ui/react/combobox";
import type * as React from "react";

import {
  ComboboxTrigger as ComboboxTriggerElement,
  type ComboboxTriggerVariantProps,
  ComboboxValue,
  ComboboxValueOverflow,
} from "../../elements/combobox";
import { ChevronDownOutline } from "../../icons";
import { Icon } from "../../internal/icon";

export type {
  ComboboxTriggerAnySize,
  ComboboxTriggerPillSize,
  ComboboxTriggerVariant,
  ComboboxTriggerVariantProps,
  ComboboxTriggerWidth,
} from "../../elements/combobox";

type ComboboxTriggerBaseProps = Omit<
  BaseCombobox.Trigger.Props,
  "children" | "className" | "style" | "render"
> & {
  /** Shown in the trigger while nothing is selected — Base UI's `Combobox.Value` placeholder. */
  placeholder?: React.ReactNode;
  /** Non-interactive selected-value preview. Omit to use Base UI's labels or placeholder. */
  children?: React.ReactNode;
  /** Non-interactive overflow summary, kept visible when the value preview truncates. */
  overflow?: React.ReactNode;
  /** Decorative leading element at the inline-start, e.g. `<Icon icon={Plus} tint="placeholder" />`. */
  icon?: React.ReactNode;
  /**
   * Decorative trailing glyph. Omit it to show a chevron (the Figma end node) — except on `pill`,
   * which follows Pill anatomy and shows no glyph unless one is passed. This is not a nested
   * popup-trigger control — the frame itself is the `Trigger`.
   */
  trailing?: React.ReactNode;
};

/**
 * `variant` is the trigger's look: `secondary` (default) is the bordered field surface, `ghost`
 * drops the border and fill, and `pill` hugs its value with outline Pill chrome. `secondary` and
 * `ghost` take `size` `md`–`2xl`; `pill` takes Pill's `xs`–`md`. Invalid on ghost has no trigger
 * chrome — the danger cue is the helper text below. Field-style triggers take `width="auto"` (the
 * existing 288px minimum) or `width="fit"` (intrinsic content width).
 */
export type ComboboxTriggerProps = ComboboxTriggerBaseProps & ComboboxTriggerVariantProps;

/**
 * The ready-made closed-field trigger: grafts Base UI's `Trigger` onto the styled frame and shows
 * the selected value (or `placeholder`) plus a trailing chevron. The `pill` variant, like
 * `SelectTrigger`'s, has no automatic chevron: its open state shows as active chrome. Use this
 * instead of `ComboboxInputGroup` when the filter input lives in the panel (`ComboboxSearch`).
 */
export function ComboboxTrigger({
  size,
  variant,
  width,
  placeholder,
  icon,
  trailing,
  children,
  overflow,
  ...props
}: ComboboxTriggerProps) {
  return (
    <BaseCombobox.Trigger
      {...props}
      render={
        variant === "pill" ? (
          <ComboboxTriggerElement size={size} variant="pill" />
        ) : (
          <ComboboxTriggerElement size={size} variant={variant} width={width} />
        )
      }
    >
      {icon}
      <ComboboxValue>
        {children === undefined ? <BaseCombobox.Value placeholder={placeholder} /> : children}
      </ComboboxValue>
      {overflow != null ? <ComboboxValueOverflow>{overflow}</ComboboxValueOverflow> : null}
      {trailing ??
        (variant !== "pill" ? (
          <Icon tint="secondary">
            <ChevronDownOutline aria-hidden />
          </Icon>
        ) : null)}
    </BaseCombobox.Trigger>
  );
}
