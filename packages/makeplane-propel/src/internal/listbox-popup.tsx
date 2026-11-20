import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";
import { cva } from "class-variance-authority";

/**
 * The shared anchored-listbox surface, grafted onto any Base UI `*.Popup` behavior in `components`
 * (`<BaseAutocomplete.Popup render={<ListboxPopup />}>`). A scrollable floating card sized to its
 * anchor: as tall as the room the positioner measured (the viewport less the dropdown edge gap,
 * `internal/dropdown-edge-gap`), at least as wide as the anchor, with the standard overlay
 * border/shadow/radius. Now used by the autocomplete family (`AutocompleteContent`,
 * `AutocompleteField`); Combobox and Select render the shared `internal/overlay-panel` card
 * instead. `origin-(--transform-origin)` is harmless when the surface is not animated.
 *
 * `bg-surface-1` (the white floating-card fill) matches the regular dropdown/menu surface — those
 * float on `surface-1` via `internal/surface`, so a listbox on the page-depth `layer-1` grey read
 * as a different, wrong color next to them.
 */
export const listboxPopupVariants = cva(
  "max-h-(--available-height) min-w-(--anchor-width) origin-(--transform-origin) overflow-y-auto rounded-md border-sm border-subtle bg-surface-1 p-1 shadow-overlay-100",
);

export type ListboxPopupProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

export function ListboxPopup({ render, ...props }: ListboxPopupProps) {
  const defaultProps: useRender.ElementProps<"div"> = { className: listboxPopupVariants() };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
