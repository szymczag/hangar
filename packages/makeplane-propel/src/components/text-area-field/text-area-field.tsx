import { Field as BaseField } from "@base-ui/react/field";
import type * as React from "react";

import { FieldControlContent } from "../../elements/field/field-control-content";
import { TextAreaField as TextAreaFieldElement } from "../../elements/text-area-field/text-area-field";
import { TextAreaGroup } from "../../elements/text-area/text-area-group";
import { FieldHelperText } from "../field/field-helper-text";
import { FieldLabelGroup } from "../field/field-label-group";
import { TextArea, type TextAreaProps, type TextAreaResize, type TextAreaSize } from "../text-area";

export type { TextAreaResize };

/** The field's size scale: the framed sizes only — the 12px `md` leaf has no field frame. */
export type TextAreaFieldSize = Exclude<TextAreaSize, "md">;

export type TextAreaFieldProps = Omit<TextAreaProps, "size" | "surface"> & {
  /** Size scale. `lg` | `xl` | `2xl`. */
  size: TextAreaFieldSize;
  /**
   * Native resize handle on the bordered frame. Forced to `none` when `autoResize` is set, so the
   * drag handle does not fight content-driven height.
   *
   * @default "vertical"
   */
  resize?: TextAreaResize;
  /**
   * Grow the control with its value, using the size min-height as the floor. Disables the native
   * resize handle.
   *
   * @default false
   */
  autoResize?: boolean;
  /**
   * Maximum visible lines when `autoResize` is set. Further lines scroll inside the control.
   * Unbounded when omitted.
   */
  maxRows?: number;
  /** Label text shown above the control. */
  label?: string;
  /**
   * Marks the field required: adds a `*` asterisk and sets `aria-required`. The native `required`
   * attribute is deliberately not rendered, so browser constraint validation never intercepts form
   * submits ahead of the app's own validation.
   */
  required?: boolean;
  /** Supporting text shown directly below the label. */
  description?: React.ReactNode;
  /** Helper text shown below the control. Replaced by `error` when an error is set. */
  hint?: React.ReactNode;
  /**
   * Error text shown below the control. Overrides `hint` and marks the field invalid (danger
   * border).
   */
  error?: React.ReactNode;
};

/**
 * Multi-line text field built on Base UI `Field`, rendering the control as a `<textarea>`. Vertical
 * layout only. `autoResize` grows the control with its value and disables the native resize
 * handle.
 */
export function TextAreaField({
  size,
  name,
  label,
  required,
  description,
  hint,
  error,
  disabled,
  resize,
  autoResize = false,
  ...controlProps
}: TextAreaFieldProps) {
  return (
    <BaseField.Root
      name={name}
      disabled={disabled}
      invalid={error != null || undefined}
      render={<TextAreaFieldElement />}
    >
      <FieldLabelGroup
        size={size}
        required={required}
        label={label}
        description={description}
        orientation="vertical"
      />
      <FieldControlContent orientation="vertical" size={size}>
        <TextAreaGroup resize={autoResize ? "none" : resize}>
          <TextArea
            aria-required={required || undefined}
            size={size}
            surface="field"
            autoResize={autoResize}
            {...controlProps}
          />
        </TextAreaGroup>
        <FieldHelperText size={size} hint={hint} error={error} />
      </FieldControlContent>
    </BaseField.Root>
  );
}
