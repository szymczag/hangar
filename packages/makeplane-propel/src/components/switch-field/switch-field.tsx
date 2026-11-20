import type * as React from "react";

import { FieldItemControlGroup } from "../../elements/field/field-item-control-group";
import type { FieldSize } from "../../elements/field/variants";
import { Field, FieldItem, FieldItemContent } from "../field";
import { FieldHelperText } from "../field/field-helper-text";
import { Switch, type SwitchSize, type SwitchProps } from "../switch/index";

export type SwitchFieldProps = Omit<SwitchProps, "aria-label" | "size"> & {
  /** The switch track's size. */
  switchSize: SwitchSize;
  /** Label and helper text size. */
  size: FieldSize;
  /** Helper text shown below the control. Replaced by `error` when an error is set. */
  hint?: React.ReactNode;
  /** Error text shown below the control. */
  error?: React.ReactNode;
  /** Visible field label. */
  label: string;
  /** Optional supporting text announced as the switch description. */
  description?: React.ReactNode;
};

/** Ready-to-use switch field with label, description, and helper/error text. */
export function SwitchField({
  label,
  description,
  hint,
  error,
  switchSize,
  size,
  name,
  disabled,
  ...controlProps
}: SwitchFieldProps) {
  return (
    <Field name={name} disabled={disabled} invalid={error != null || undefined}>
      <FieldItem disabled={disabled}>
        <FieldItemControlGroup>
          <Switch size={switchSize} disabled={disabled} {...controlProps} />
        </FieldItemControlGroup>
        <FieldItemContent size={size} description={description}>
          {label}
        </FieldItemContent>
      </FieldItem>
      <FieldHelperText size={size} hint={hint} error={error} />
    </Field>
  );
}
