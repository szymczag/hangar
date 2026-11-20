import {
  SelectSeparator as SelectSeparatorElement,
  type SelectSeparatorProps as SelectSeparatorElementProps,
} from "../../elements/select";

export type SelectSeparatorProps = SelectSeparatorElementProps;

/**
 * A thin divider between groups of options — the same chrome as `ComboboxSeparator` and
 * `MenuSeparator`. Purely visual, so it is `aria-hidden` and carries no `separator` role: a listbox
 * may only own options and groups, so Base UI's `Select.Separator` (which renders
 * `role="separator"`) would be invalid ARIA inside the list. The `SelectGroup` labels already give
 * a screen reader the structure the line shows.
 */
export function SelectSeparator(props: SelectSeparatorProps) {
  return <SelectSeparatorElement aria-hidden {...props} />;
}
