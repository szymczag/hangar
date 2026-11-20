import { Checkbox as BaseCheckbox } from "@base-ui/react/checkbox";
import * as React from "react";

import {
  Checkbox as CheckboxElement,
  CheckboxIndeterminateIndicator,
  CheckboxIndicator,
  CheckboxLabel,
  type CheckboxLabelStretch,
} from "../../elements/checkbox";
import { TickOutline, MinusOutline } from "../../icons";

export type CheckboxProps = Omit<BaseCheckbox.Root.Props, "className" | "style" | "render"> & {
  /**
   * Optional text shown beside the box; the whole row becomes the clickable label. Omit it for a
   * bare checkbox (just the box) — in that case give the box an accessible name with `aria-label`
   * or `aria-labelledby`.
   */
  label?: string;
  /**
   * Width of the clickable label row when `label` is present. Ready-made concern — the elements
   * `CheckboxLabel` requires `stretch` explicitly.
   *
   * @default "auto"
   */
  stretch?: CheckboxLabelStretch;
  /**
   * Element shown between the box and the label (inline-start), e.g. `<Icon icon={User}
   * tint="secondary" size="sm" />`. Only rendered when `label` is present. Prefer the shared `Icon`
   * (a direct `aria-hidden` span) so the label's disabled tint override can recolor it.
   */
  icon?: React.ReactNode;
};

/**
 * The ready-made checkbox: grafts Base UI checkbox behavior onto the styled `Checkbox` box with its
 * check and indeterminate indicators, and optionally wraps the row in a clickable `CheckboxLabel`
 * with an icon slot.
 */
export function Checkbox({ label, stretch = "auto", icon, id, ...props }: CheckboxProps) {
  // Generate a stable id so an explicit `label` can be associated with the box.
  const generatedId = React.useId();
  const checkboxId = id ?? generatedId;

  // Only force the generated id when there's a `label` to associate; without one (e.g. inside a
  // `Field`, which manages labeling), pass the caller's `id` through untouched.
  const box = (
    <BaseCheckbox.Root id={label != null ? checkboxId : id} render={<CheckboxElement />} {...props}>
      <BaseCheckbox.Indicator render={<CheckboxIndicator />}>
        <TickOutline aria-hidden />
      </BaseCheckbox.Indicator>
      <BaseCheckbox.Indicator render={<CheckboxIndeterminateIndicator />}>
        <MinusOutline aria-hidden />
      </BaseCheckbox.Indicator>
    </BaseCheckbox.Root>
  );

  if (label == null) return box;

  return (
    <CheckboxLabel htmlFor={checkboxId} stretch={stretch}>
      {box}
      {icon}
      {label}
    </CheckboxLabel>
  );
}
