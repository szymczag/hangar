import { Combobox as BaseCombobox } from "@base-ui/react/combobox";

export type ComboboxProps<Value, Multiple extends boolean | undefined = false, Item = Value> = Omit<
  BaseCombobox.Root.Props<Value, Multiple, Item>,
  "className" | "style" | "modal"
> & {
  /**
   * Whether the combobox enters a modal state when open, like `Select`: page scroll is locked and a
   * press outside the popup only dismisses it. The input (or input group) is cut out of the
   * backdrop, so filter-in-field compositions still take typing and clicks. Set `false` to leave
   * the rest of the page interactive while the list is open.
   *
   * @default true
   */
  modal?: boolean;
};

/**
 * The combobox Root — Base UI's context/state provider (renders no element of its own). A
 * behavior-only role, so it lives in `components` (rules 1a, 2); the styled parts live in
 * `elements/combobox` and are grafted onto Base UI behavior here.
 *
 * Modal by default, unlike Base UI's root. `ComboboxSubmenu` roots stay non-modal — a nested
 * backdrop would cover the parent list.
 */
export function Combobox<Value, Multiple extends boolean | undefined = false, Item = Value>({
  modal = true,
  ...props
}: ComboboxProps<Value, Multiple, Item>) {
  return <BaseCombobox.Root modal={modal} {...props} />;
}
