import { Combobox as BaseCombobox } from "@base-ui/react/combobox";

export type ComboboxListProps = Omit<BaseCombobox.List.Props, "className" | "style"> & {
  /**
   * Accessible name for the listbox. Override to localize, or pass `aria-labelledby` instead.
   *
   * @default "Suggestions"
   */
  "aria-label"?: string;
};

/**
 * The combobox items container — Base UI's `List` behavior part (it carries no propel styling of
 * its own), passed through so a full combobox composes without importing `@base-ui/react`. Inside
 * `ComboboxContent`'s overlay, this is the `role="listbox"` node; it defaults to
 * `aria-label="Suggestions"` so the listbox stays named (pass `aria-label` / `aria-labelledby` to
 * override or localize).
 */
export function ComboboxList({
  "aria-label": ariaLabel = "Suggestions",
  ...props
}: ComboboxListProps) {
  return <BaseCombobox.List aria-label={ariaLabel} {...props} />;
}
