import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import {
  type ComboboxInputGroupClearVariantProps,
  comboboxInputGroupClearVariants,
} from "./variants";

export type ComboboxInputGroupClearProps = Omit<
  useRender.ComponentProps<"span">,
  "className" | "style"
> &
  ComboboxInputGroupClearVariantProps;

/**
 * Gutter that reserves the clear control's own footprint, keeping it in layout (invisible, not
 * unmounted) whenever Base UI's `Clear` has no value to clear.
 */
export function ComboboxInputGroupClear({ render, ...props }: ComboboxInputGroupClearProps) {
  const defaultProps: useRender.ElementProps<"span"> & Record<`data-${string}`, string> = {
    // The group's own padding hugs a `<button>` descendant (`has-[button]:pr-1`). Clear is grafted
    // with `keepMounted` (invisible at an empty value, never removed), so the button is always
    // present for that selector — `data-slot` still marks this gutter explicitly, and the slot's
    // `invisible` rule keys off the child's `data-visible` rather than mount state.
    "data-slot": "clear",
    className: comboboxInputGroupClearVariants(),
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
