import { Select as BaseSelect } from "@base-ui/react/select";

import { SelectLabel as SelectLabelElement, type SelectLabelSize } from "../../elements/select";

export type SelectLabelProps = Omit<BaseSelect.Label.Props, "className" | "render" | "style"> & {
  /** Label text size. Pass the same step as the `SelectTrigger` it labels. Required. */
  size: SelectLabelSize;
};

/**
 * The ready-made select label: grafts Base UI's `Select.Label` behavior — automatic association
 * with the trigger — onto the styled label.
 */
export function SelectLabel({ size, ...props }: SelectLabelProps) {
  return <BaseSelect.Label {...props} render={<SelectLabelElement size={size} />} />;
}
