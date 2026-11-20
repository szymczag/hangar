import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { autocompleteInputVariants } from "./variants";

// The native `<input size>` (width in characters) is omitted: a styled field never sizes itself
// that way, and the text size comes from the group (see `autocompleteInputVariants`).
export type AutocompleteInputProps = Omit<
  useRender.ComponentProps<"input">,
  "className" | "style" | "size"
>;

/**
 * The styled autocomplete text field. Base-UI-agnostic — graft the combobox behavior in
 * `components` via `<BaseAutocomplete.Input render={<AutocompleteInput/>} />`.
 */
export function AutocompleteInput({ render, ...props }: AutocompleteInputProps) {
  const defaultProps: useRender.ElementProps<"input"> = {
    className: autocompleteInputVariants(),
  };
  return useRender({ defaultTagName: "input", render, props: mergeProps(defaultProps, props) });
}
