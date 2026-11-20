import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import {
  type ComboboxSubmenuTriggerVariantProps,
  comboboxSubmenuTriggerVariants,
} from "./variants";

export type { ComboboxSubmenuTriggerVariant } from "./variants";

export type ComboboxSubmenuTriggerProps = Omit<
  useRender.ComponentProps<"div">,
  "className" | "style"
> &
  ComboboxSubmenuTriggerVariantProps;

/**
 * The styled row that opens a nested combobox. Base-UI-agnostic — the behavior is grafted in
 * `components` via `<BaseCombobox.Item render={<ComboboxSubmenuTrigger />} />`, because the row
 * belongs to the PARENT list (it must stay highlightable and filterable there) while the nested
 * list is a combobox of its own. Same menu-row chrome as `ComboboxItem`, plus the `data-popup-open`
 * highlight that keeps the row lit while its nested list sits open beside it.
 */
export function ComboboxSubmenuTrigger({ variant, render, ...props }: ComboboxSubmenuTriggerProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: comboboxSubmenuTriggerVariants({ variant }),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
