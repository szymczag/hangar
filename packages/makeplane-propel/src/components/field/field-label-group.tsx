import type * as React from "react";

import { FieldLabelGroup as FieldLabelGroupContainer } from "../../elements/field/field-label-group";
import { type FieldLabelGroupVariantProps, type FieldSize } from "../../elements/field/variants";
import { FieldDescription } from "./field-description";
import { FieldLabel } from "./field-label";

export type FieldLabelGroupProps = FieldLabelGroupVariantProps & {
  size: FieldSize;
  required?: boolean;
  label?: string;
  description?: React.ReactNode;
};

/**
 * The ready-made label/description block of a field: lays out an optional `FieldLabel` and
 * `FieldDescription` inside the `FieldLabelGroup` container. Renders nothing when both are absent.
 */
export function FieldLabelGroup({
  size,
  required,
  label,
  description,
  orientation,
}: FieldLabelGroupProps) {
  if (label == null && description == null) {
    return null;
  }
  const inset = orientation === "horizontal" && description == null;
  return (
    <FieldLabelGroupContainer orientation={orientation}>
      {label != null ? (
        <FieldLabel size={size} required={required} inset={inset}>
          {label}
        </FieldLabel>
      ) : null}
      {description != null ? <FieldDescription size={size}>{description}</FieldDescription> : null}
    </FieldLabelGroupContainer>
  );
}
