import { Fieldset as BaseFieldset } from "@base-ui/react/fieldset";
import type * as React from "react";

import type { FieldSize } from "../../elements/field/variants";
import { FieldsetLegend } from "../../elements/fieldset/index";
import { FieldOptionSizeProvider } from "../../internal/field-option-size";
import { CheckboxGroup, type CheckboxGroupProps } from "../checkbox-group/index";
import { Field, FieldDescription } from "../field";
import { FieldHelperText } from "../field/field-helper-text";

export type CheckboxGroupFieldProps = Omit<CheckboxGroupProps, "children" | "density" | "name"> & {
  /** Checkbox option rows, usually `CheckboxGroupFieldOption`. */
  children: React.ReactNode;
  /** Spacing between checkbox options. */
  density: CheckboxGroupProps["density"];
  /** Supporting text shown below the legend. */
  description?: React.ReactNode;
  /** Error text shown below the group. */
  error?: React.ReactNode;
  /** Helper text shown below the group. Replaced by `error` when an error is set. */
  hint?: React.ReactNode;
  /** Visible fieldset legend. */
  label: string;
  /** Legend and helper text size. */
  size: FieldSize;
  /** Submitted field name. */
  name: string;
};

/** Ready-to-use checkbox group field with legend, description, and helper/error text. */
export function CheckboxGroupField({
  children,
  density,
  description,
  disabled,
  error,
  hint,
  label,
  size,
  name,
  ...groupProps
}: CheckboxGroupFieldProps) {
  return (
    <Field name={name} disabled={disabled} invalid={error != null || undefined}>
      <BaseFieldset.Root
        render={<CheckboxGroup density={density} disabled={disabled} {...groupProps} />}
      >
        <BaseFieldset.Legend render={<FieldsetLegend size={size} />}>{label}</BaseFieldset.Legend>
        {description != null ? (
          <FieldDescription size={size}>{description}</FieldDescription>
        ) : null}
        <FieldOptionSizeProvider size={size}>{children}</FieldOptionSizeProvider>
      </BaseFieldset.Root>
      <FieldHelperText size={size} hint={hint} error={error} />
    </Field>
  );
}
