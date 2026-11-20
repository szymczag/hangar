import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type ComboboxChipVariantProps, comboboxChipVariants } from "./variants";

export type { ComboboxChipSize } from "./variants";

export type ComboboxChipProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  ComboboxChipVariantProps;

/**
 * One selected value in the multiselect frame, shown as a removable tag: its label plus a remove
 * control (an `IconButton` grafted onto Base UI's `ChipRemove` by the `components` ready-made).
 * Arrow keys move focus across chips (Base UI's behavior), so it carries the standard focus ring.
 * Base-UI-agnostic — graft in `components` via `<BaseCombobox.Chip render={<ComboboxChip/>} />`.
 */
export function ComboboxChip({ render, size, ...props }: ComboboxChipProps) {
  const defaultProps: useRender.ElementProps<"div"> = { className: comboboxChipVariants({ size }) };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
