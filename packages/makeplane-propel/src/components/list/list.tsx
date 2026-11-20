import { Composite, type CompositeProps } from "../../base/composite";
import { List as ListElement } from "../../elements/list/list";
import type { ListVariantProps } from "../../elements/list/variants";
export type { ListGap } from "../../elements/list/variants";

export type ListProps = Omit<CompositeProps, "className" | "style" | "render"> & ListVariantProps;

/**
 * A vertical roving-tabindex list — the primitive sidebars compose. Base UI's `Composite`
 * roving-focus behavior grafted onto the styled `elements` `List` element (rule 1a). One tab stop
 * for the whole list; arrow keys move between every `CompositeItem` in document order — row
 * primaries (`ListItemLink` / `ListItemButton`) and sibling controls that opt in
 * (`ListItemDisclosureTrigger`). Role-flexible: pass the `role`/`aria-*` the context calls for.
 * Compose `ListItem` rows inside. The `gap` prop controls row spacing.
 *
 * @default gap="0.5"
 */
export function List({ gap, ...props }: ListProps) {
  return <Composite {...props} render={<ListElement gap={gap} />} />;
}
