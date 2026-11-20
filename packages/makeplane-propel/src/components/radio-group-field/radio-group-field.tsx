import { Fieldset as BaseFieldset } from "@base-ui/react/fieldset";
import type * as React from "react";

import type { FieldSize } from "../../elements/field/variants";
import { FieldsetLegend } from "../../elements/fieldset/index";
import { RadioGroupOptions, type RadioGroupOptionsOrientation } from "../../elements/radio/index";
import { FieldOptionSizeProvider } from "../../internal/field-option-size";
import { Field, FieldDescription } from "../field";
import { FieldHelperText } from "../field/field-helper-text";
import { RadioGroup, type RadioGroupProps } from "../radio/index";

export type RadioGroupFieldProps<Value = string> = Omit<
  RadioGroupProps<Value>,
  "children" | "density" | "name"
> & {
  /** Radio option rows, usually `RadioGroupFieldOption`. */
  children: React.ReactNode;
  /** Spacing between radio options. */
  density: RadioGroupProps<Value>["density"];
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
  /** Arrangement of the radio option rows. @default "vertical" */
  orientation?: RadioGroupOptionsOrientation;
};

/** Ready-to-use radio group field with legend, description, and helper/error text. */
export function RadioGroupField<Value = string>({
  children,
  density,
  description,
  disabled,
  error,
  hint,
  label,
  size,
  name,
  orientation,
  required,
  ...groupProps
}: RadioGroupFieldProps<Value>) {
  return (
    <Field name={name} disabled={disabled} invalid={error != null || undefined}>
      <BaseFieldset.Root
        render={
          <RadioGroup<Value>
            density={density}
            disabled={disabled}
            required={required}
            {...groupProps}
            aria-orientation={orientation === "horizontal" ? "horizontal" : undefined}
          />
        }
      >
        <BaseFieldset.Legend render={<FieldsetLegend size={size} />}>{label}</BaseFieldset.Legend>
        {description != null ? (
          <FieldDescription size={size}>{description}</FieldDescription>
        ) : null}
        <RadioGroupOptions density={density} orientation={orientation}>
          <FieldOptionSizeProvider size={size}>{children}</FieldOptionSizeProvider>
        </RadioGroupOptions>
      </BaseFieldset.Root>
      <FieldHelperText size={size} hint={hint} error={error} />
    </Field>
  );
}
