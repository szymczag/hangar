import { NumberField as BaseNumberField } from "@base-ui/react/number-field";
import type * as React from "react";

import {
  NumberField as NumberFieldElement,
  NumberFieldGroup,
  NumberFieldInput,
  type NumberFieldSize,
} from "../../elements/number-field";

export type { NumberFieldSize, NumberFieldStepperSize } from "../../elements/number-field";
export { numberFieldStepperSize } from "../../elements/number-field";

type NumberFieldNamedProps =
  | {
      /** Accessible name for the value input. Required when `aria-labelledby` is omitted. */
      "aria-label": string;
      /** Id of a visible label element. Optional when `aria-label` is set. */
      "aria-labelledby"?: string;
    }
  | {
      /** Accessible name for the value input. Optional when `aria-labelledby` is set. */
      "aria-label"?: string;
      /** Id of a visible label element. Required when `aria-label` is omitted. */
      "aria-labelledby": string;
    };

export type NumberFieldProps = Omit<
  BaseNumberField.Root.Props,
  "className" | "style" | "render" | "size" | "aria-label" | "aria-labelledby"
> & {
  /**
   * Visual size of the field frame (`sm` 24 / `md` 28 / `lg` 32). Pair steppers with
   * {@link numberFieldStepperSize}`[size]` — button size is one rung below the field.
   */
  size: NumberFieldSize;
  /**
   * The decrement control (e.g. an `IconButton`), rendered as the field's decrement stepper. It
   * carries its own — localizable — `aria-label`; the field bakes no label or glyph.
   */
  decrement: React.ReactElement;
  /**
   * The increment control (e.g. an `IconButton`), rendered as the field's increment stepper. It
   * carries its own — localizable — `aria-label`; the field bakes no label or glyph.
   */
  increment: React.ReactElement;
} & NumberFieldNamedProps;

/**
 * The ready-made number field: a numeric input flanked by decrement / increment buttons. Drive it
 * with `value`/`defaultValue` + `onValueChange`, bound it with `min`/`max`/`step`, and pass
 * `format` (an `Intl.NumberFormatOptions`) to format the displayed value. Name the input with
 * `aria-label` or `aria-labelledby` — the ready-made has no baked visible label.
 *
 * Grafts Base UI `NumberField` behavior onto the `elements/number-field` styled parts
 * (`NumberField` root + `NumberFieldGroup` + `NumberFieldInput`) via `render`. The
 * `decrement`/`increment` steppers are consumer-provided controls, grafted onto Base UI's
 * `Decrement`/`Increment` behavior.
 */
export function NumberField({
  "aria-label": ariaLabel,
  "aria-labelledby": ariaLabelledby,
  size,
  decrement,
  increment,
  ...props
}: NumberFieldProps) {
  return (
    <BaseNumberField.Root {...props} render={<NumberFieldElement />}>
      <BaseNumberField.Group render={<NumberFieldGroup size={size} />}>
        <BaseNumberField.Decrement render={decrement} />
        {/* The accessible name belongs on the input, not the root div. */}
        <BaseNumberField.Input
          render={
            <NumberFieldInput size={size} aria-label={ariaLabel} aria-labelledby={ariaLabelledby} />
          }
        />
        <BaseNumberField.Increment render={increment} />
      </BaseNumberField.Group>
    </BaseNumberField.Root>
  );
}
