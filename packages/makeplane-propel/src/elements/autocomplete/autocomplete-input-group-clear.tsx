import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import {
  type AutocompleteInputGroupClearVariantProps,
  autocompleteInputGroupClearVariants,
} from "./variants";

export type AutocompleteInputGroupClearProps = Omit<
  useRender.ComponentProps<"span">,
  "className" | "style"
> &
  AutocompleteInputGroupClearVariantProps;

/**
 * Gutter that reserves the clear control's own footprint, keeping it in layout (invisible, not
 * unmounted) whenever Base UI's `Clear` has no value to clear.
 */
export function AutocompleteInputGroupClear({
  render,
  ...props
}: AutocompleteInputGroupClearProps) {
  const defaultProps: useRender.ElementProps<"span"> & Record<`data-${string}`, string> = {
    // The group's own padding hugs a `<button>` descendant (`has-[button]:pe-1`). Clear is grafted
    // with `keepMounted` (invisible at an empty value, never removed), so the button is always
    // present for that selector — `data-slot` still marks this gutter explicitly, and the slot's
    // `invisible` rule keys off the child's `data-visible` rather than mount state.
    "data-slot": "clear",
    className: autocompleteInputGroupClearVariants(),
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
