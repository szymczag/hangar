import { Select as BaseSelect } from "@base-ui/react/select";
import type * as React from "react";

import { SelectMultipleContext } from "./select-multiple-context";

export type SelectProps<Value, Multiple extends boolean | undefined = false> = Omit<
  BaseSelect.Root.Props<Value, Multiple>,
  "className" | "style"
> & {
  /** The select's anatomy — a `SelectTrigger` and the popup of items. */
  children?: React.ReactNode;
};

/**
 * The select Root — Base UI's context/state provider (renders no element of its own). A
 * behavior-only role, so it lives in `components` (rules 1a, 2); the styled parts live in
 * `elements/select` and are grafted onto Base UI behavior here. It also shares `multiple` with its
 * `SelectItem`s, which switch to a leading checkbox marker for a multi-select.
 */
export function Select<Value, Multiple extends boolean | undefined = false>(
  props: SelectProps<Value, Multiple>,
) {
  return (
    <SelectMultipleContext.Provider value={props.multiple === true}>
      <BaseSelect.Root {...props} />
    </SelectMultipleContext.Provider>
  );
}
