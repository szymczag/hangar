import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import {
  type AutocompleteInputGroupVariantProps,
  autocompleteInputGroupVariants,
} from "./variants";

export type { AutocompleteSize } from "./variants";

export type AutocompleteInputGroupProps = Omit<
  useRender.ComponentProps<"div">,
  "className" | "style"
> &
  AutocompleteInputGroupVariantProps;

/**
 * The styled bordered frame around the input + its adornments. Base-UI-agnostic — graft in
 * `components` via `<BaseAutocomplete.InputGroup render={<AutocompleteInputGroup/>} />`.
 */
export function AutocompleteInputGroup({ size, render, ...props }: AutocompleteInputGroupProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: autocompleteInputGroupVariants({ size }),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
