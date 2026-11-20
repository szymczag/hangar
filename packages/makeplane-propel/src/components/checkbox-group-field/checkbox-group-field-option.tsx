import type * as React from "react";

import { FieldItemControlGroup } from "../../elements/field/field-item-control-group";
import type { FieldSize } from "../../elements/field/variants";
import { useFieldOptionSize } from "../../internal/field-option-size";
import { Checkbox, type CheckboxProps } from "../checkbox";
import { FieldItem, FieldItemContent } from "../field";

/** Bare checkbox control props for a field row — no chip `label` / `icon` (Field owns labeling). */
type CheckboxFieldControlProps = Omit<CheckboxProps, "children" | "label" | "icon">;

export type CheckboxGroupFieldOptionProps = Omit<CheckboxFieldControlProps, "aria-label"> & {
  /** Visible option label. */
  label: string;
  /** Optional supporting text announced as the checkbox description. */
  description?: React.ReactNode;
  /** Label and description size. Inherited from `CheckboxGroupField` when omitted. */
  size?: FieldSize;
};

/** A checkbox option row for use inside `CheckboxGroupField` or a custom `CheckboxGroup`. */
export function CheckboxGroupFieldOption({
  label,
  description,
  size: sizeProp,
  ...props
}: CheckboxGroupFieldOptionProps) {
  const size = useFieldOptionSize(sizeProp);

  return (
    <FieldItem disabled={props.disabled}>
      <FieldItemControlGroup>
        <Checkbox {...props} />
      </FieldItemControlGroup>
      <FieldItemContent size={size} description={description}>
        {label}
      </FieldItemContent>
    </FieldItem>
  );
}
