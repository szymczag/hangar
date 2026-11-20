import type * as React from "react";

import { FieldItemControlGroup } from "../../elements/field/field-item-control-group";
import type { FieldSize } from "../../elements/field/variants";
import { useFieldOptionSize } from "../../internal/field-option-size";
import { FieldItem, FieldItemContent } from "../field";
import { Radio, type RadioProps } from "../radio/radio";

export type RadioGroupFieldOptionProps = RadioProps & {
  /** Visible option label. */
  label: string;
  /** Optional supporting text announced as the radio description. */
  description?: React.ReactNode;
  /** Label and description size. Inherited from `RadioGroupField` when omitted. */
  size?: FieldSize;
};

/** A radio option row for use inside `RadioGroupField` or a custom `RadioGroup`. */
export function RadioGroupFieldOption({
  label,
  description,
  size: sizeProp,
  ...props
}: RadioGroupFieldOptionProps) {
  const size = useFieldOptionSize(sizeProp);

  return (
    <FieldItem disabled={props.disabled}>
      <FieldItemControlGroup>
        <Radio {...props} />
      </FieldItemControlGroup>
      <FieldItemContent size={size} description={description}>
        {label}
      </FieldItemContent>
    </FieldItem>
  );
}
