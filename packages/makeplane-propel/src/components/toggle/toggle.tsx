import { Toggle as BaseToggle } from "@base-ui/react/toggle";
import type { Toggle as BaseToggleTypes } from "@base-ui/react/toggle";
import type * as React from "react";

import { Toggle as ToggleElement, ToggleLabel, type ToggleSize } from "../../elements/toggle";

export type ToggleProps<Value extends string = string> = Omit<
  BaseToggleTypes.Props<Value>,
  "children" | "className" | "style"
> & {
  /**
   * Label-toggle scale (`xs`·`sm`·`md`).
   *
   * @default "md"
   */
  size?: ToggleSize;
  /** Element rendered before the label (inline-start), e.g. `<Icon icon={Tag} />`. */
  startIcon?: React.ReactNode;
  /** Element rendered after the label (inline-end), e.g. `<Icon icon={X} />`. */
  endIcon?: React.ReactNode;
  /** Visible toggle label. */
  label: string;
};

/**
 * The ready-made label toggle: grafts Base UI's `Toggle` behavior onto the styled `Toggle` button
 * (behavior outer, the styled button as the render target), with an optional leading node, the
 * `ToggleLabel`, and an optional trailing node. The selected look is the container's pressed
 * state.
 */
export function Toggle<Value extends string = string>({
  size,
  startIcon,
  endIcon,
  label,
  ...toggleProps
}: ToggleProps<Value>) {
  return (
    <BaseToggle {...toggleProps} render={<ToggleElement size={size} />}>
      {startIcon}
      <ToggleLabel>{label}</ToggleLabel>
      {endIcon}
    </BaseToggle>
  );
}
