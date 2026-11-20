import { Fieldset as BaseFieldset } from "@base-ui/react/fieldset";
import type * as React from "react";

import {
  Fieldset as FieldsetElement,
  type FieldsetProps as FieldsetElementProps,
  FieldsetBody,
  FieldsetDescription,
  FieldsetLegend,
  type FieldsetLegendProps,
} from "../../elements/fieldset";

export type FieldsetProps = FieldsetElementProps & {
  /** Supporting text shown below the legend. */
  description?: React.ReactNode;
  /** The legend text labelling the group. */
  legend: React.ReactNode;
  /** Text size for the legend block — the legend and, when present, its description. */
  legendSize: FieldsetLegendProps["size"];
  /** The grouped controls. */
  children: React.ReactNode;
};

/**
 * The ready-made fieldset: groups a `legend` with its related controls for the 90% case. Grafts
 * Base UI's `Fieldset` behavior onto propel's styled parts — pass the legend text, `legendSize`,
 * and whether the group is `bordered`; everything else flows through to the underlying fieldset
 * root.
 */
export function Fieldset({
  bordered,
  description,
  legend,
  legendSize,
  children,
  ...props
}: FieldsetProps) {
  return (
    <BaseFieldset.Root {...props} render={<FieldsetElement bordered={bordered} />}>
      <BaseFieldset.Legend render={<FieldsetLegend size={legendSize} />}>
        {legend}
      </BaseFieldset.Legend>
      {description != null ? (
        <FieldsetDescription size={legendSize}>{description}</FieldsetDescription>
      ) : null}
      <FieldsetBody>{children}</FieldsetBody>
    </BaseFieldset.Root>
  );
}
