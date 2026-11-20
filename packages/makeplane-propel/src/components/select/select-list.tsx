import { Select as BaseSelect } from "@base-ui/react/select";

import { SelectList as SelectListElement } from "../../elements/select";

export type SelectListProps = Omit<BaseSelect.List.Props, "className" | "render" | "style">;

/**
 * The container for the select items: Base UI's `Select.List` grafted onto the styled `SelectList`,
 * the padded list inside the `SelectContent` panel (the rows are `SelectItem`s).
 */
export function SelectList(props: SelectListProps) {
  return <BaseSelect.List {...props} render={<SelectListElement />} />;
}
