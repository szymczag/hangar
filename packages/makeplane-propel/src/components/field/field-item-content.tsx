import type * as React from "react";

import { FieldItemContent as FieldItemContentElement } from "../../elements/field/field-item-content";
import { type FieldSize } from "../../elements/field/variants";
import { FieldDescription } from "./field-description";
import { FieldLabel } from "./field-label";

/** The label + description column for a single choice option (checkbox/radio/switch row). */
export function FieldItemContent({
  children,
  description,
  size,
}: {
  children: React.ReactNode;
  description?: React.ReactNode;
  size: FieldSize;
}) {
  return (
    <FieldItemContentElement>
      <FieldLabel size={size} inset={false}>
        {children}
      </FieldLabel>
      {description != null ? <FieldDescription size={size}>{description}</FieldDescription> : null}
    </FieldItemContentElement>
  );
}
