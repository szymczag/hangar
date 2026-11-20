import { Autocomplete as BaseAutocomplete } from "@base-ui/react/autocomplete";
import type * as React from "react";

import {
  ListboxGroupLabel,
  ListboxGroupLabelMeta,
  ListboxGroupLabelTitle,
} from "../../internal/listbox-group-label";
import { rendersContent } from "../../internal/renders-content";

export type AutocompleteGroupLabelProps = Omit<
  BaseAutocomplete.GroupLabel.Props,
  "className" | "style" | "render"
> & {
  /** Content pinned at the heading's inline end, e.g. a count or a "Clear" action. */
  meta?: React.ReactNode;
};

/**
 * The muted heading naming a `AutocompleteGroup`, with optional `meta` pinned at its end. Base UI's
 * `GroupLabel` behavior is grafted onto the heading's TITLE, not the whole row, so the group's
 * accessible name is the heading text alone — a count or a "Clear" button in `meta` stays out of
 * it. Place it inside the `AutocompleteGroup` it names, so Base UI wires it as that group's label.
 */
export function AutocompleteGroupLabel({ meta, ...props }: AutocompleteGroupLabelProps) {
  return (
    <ListboxGroupLabel>
      <BaseAutocomplete.GroupLabel {...props} render={<ListboxGroupLabelTitle />} />
      {rendersContent(meta) ? <ListboxGroupLabelMeta>{meta}</ListboxGroupLabelMeta> : null}
    </ListboxGroupLabel>
  );
}
