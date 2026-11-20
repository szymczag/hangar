import { Select as BaseSelect } from "@base-ui/react/select";
import type * as React from "react";

import {
  SelectTrigger as SelectTriggerElement,
  type SelectTriggerVariantProps,
  SelectValue,
} from "../../elements/select";
import { ChevronDownOutline } from "../../icons";
import { Icon as IconSlot } from "../../internal/icon";

type SelectTriggerBaseProps = Omit<
  BaseSelect.Trigger.Props,
  "children" | "className" | "render" | "style"
> & {
  /** Shown in the trigger while nothing is selected — Base UI's `Select.Value` placeholder. */
  placeholder?: React.ReactNode;
  /** Element shown before the value, e.g. `<Icon icon={Server} tint="placeholder" />`. */
  icon?: React.ReactNode;
};

export type SelectTriggerProps = SelectTriggerBaseProps & SelectTriggerVariantProps;

/**
 * The ready-made select trigger: grafts Base UI's `Select.Trigger` behavior onto the styled trigger
 * and bakes its anatomy — an optional leading icon, the selected value (Base UI's `Select.Value`
 * grafted onto `SelectValue`), and an owned chevron indicator for field-style variants. The `pill`
 * variant follows Propel Pill anatomy and has no baked trailing icon; its open state is conveyed by
 * active chrome. Children are baked, so the prop is omitted.
 */
export function SelectTrigger({
  size,
  variant,
  width,
  placeholder,
  icon,
  ...props
}: SelectTriggerProps) {
  const triggerElement =
    variant === "pill" ? (
      <SelectTriggerElement size={size} variant="pill" />
    ) : (
      <SelectTriggerElement size={size} variant={variant} width={width} />
    );

  return (
    <BaseSelect.Trigger {...props} render={triggerElement}>
      {icon}
      <BaseSelect.Value render={<SelectValue />} placeholder={placeholder} />
      {variant !== "pill" ? (
        <IconSlot tint="secondary">
          <ChevronDownOutline aria-hidden />
        </IconSlot>
      ) : null}
    </BaseSelect.Trigger>
  );
}
