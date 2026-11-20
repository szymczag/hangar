import { ToggleGroup as BaseToggleGroup } from "@base-ui/react/toggle-group";
import { Toolbar as BaseToolbar } from "@base-ui/react/toolbar";

import { ToolbarToggleGroup as ToolbarToggleGroupElement } from "../../elements/toolbar";

export type ToolbarToggleGroupProps<Value extends string = string> = Omit<
  BaseToggleGroup.Props<Value>,
  "className" | "style" | "render" | "aria-label"
> & {
  /** Accessible name for the toggle cluster. */
  "aria-label": string;
};

/**
 * A cluster of `ToolbarToggle`s sharing one selection: grafts Base UI `Toolbar.Group` (toolbar
 * group semantics + group `disabled`) and `ToggleGroup` (value state) onto the styled toggle-group
 * container. Drive it with `value`/`defaultValue` + `onValueChange`. An `aria-label` is required.
 */
export function ToolbarToggleGroup<Value extends string = string>({
  disabled,
  ...props
}: ToolbarToggleGroupProps<Value>) {
  return (
    <BaseToolbar.Group
      disabled={disabled}
      render={
        <BaseToggleGroup {...props} disabled={disabled} render={<ToolbarToggleGroupElement />} />
      }
    />
  );
}
