import { Toggle as BaseToggle } from "@base-ui/react/toggle";
import type { Toggle as BaseToggleTypes } from "@base-ui/react/toggle";
import type * as React from "react";

import {
  IconToggle as IconToggleElement,
  type IconToggleVariant,
  type ToggleSize,
} from "../../elements/toggle";

export type IconToggleProps<Value extends string = string> = Omit<
  BaseToggleTypes.Props<Value>,
  "children" | "className" | "style"
> & {
  /**
   * Look: raised bordered (`secondary`) or transparent (`ghost`).
   *
   * @default "secondary"
   */
  variant?: IconToggleVariant;
  /**
   * Square scale (`xs`·`sm`·`md`).
   *
   * @default "md"
   */
  size?: ToggleSize;
  /** Icon element rendered inside the toggle, usually `<Icon icon={...} />`. */
  icon: React.ReactNode;
  /** Required: icon-only toggles have no visible text, so they must be labeled. */
  "aria-label": string;
};

/**
 * The ready-made icon-only toggle: grafts Base UI's `Toggle` behavior onto the styled `IconToggle`
 * button (behavior outer, the styled button as the render target).
 */
export function IconToggle<Value extends string = string>({
  variant,
  size,
  icon,
  ...toggleProps
}: IconToggleProps<Value>) {
  return (
    <BaseToggle {...toggleProps} render={<IconToggleElement variant={variant} size={size} />}>
      {icon}
    </BaseToggle>
  );
}
