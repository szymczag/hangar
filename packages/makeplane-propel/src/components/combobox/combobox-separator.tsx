import {
  ComboboxSeparator as ComboboxSeparatorElement,
  type ComboboxSeparatorProps as ComboboxSeparatorElementProps,
} from "../../elements/combobox";

export type ComboboxSeparatorProps = ComboboxSeparatorElementProps;

/**
 * A thin divider between groups of items in a combobox list — the same chrome as `MenuSeparator`.
 * Base UI's combobox has no Separator primitive, so this is the styled element composed into the
 * list.
 */
export function ComboboxSeparator(props: ComboboxSeparatorProps) {
  return <ComboboxSeparatorElement {...props} />;
}
