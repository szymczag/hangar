import { Collapsible as BaseCollapsible } from "@base-ui/react/collapsible";

import { CompositeItem } from "../../base/composite";
import { ListItemDisclosureTrigger as ListItemDisclosureTriggerElement } from "../../elements/list/list-item-disclosure-trigger";
import { ChevronDownOutline } from "../../icons";
import { DisclosureIndicator } from "../../internal/disclosure-indicator";

export type ListItemDisclosureTriggerProps = Omit<
  BaseCollapsible.Trigger.Props,
  "className" | "style" | "render" | "children"
> & {
  /** Required: the trigger has no visible text (just the caret), so it must be labeled. */
  "aria-label": string;
};

/**
 * A row's expand/collapse control — Base UI `Collapsible.Trigger` grafted onto the styled
 * trailing-edge element (rule 1a), with the shared rotating caret baked in, and registered as a
 * roving `CompositeItem` so it participates in the parent `List`'s one-tab-stop / arrow-key
 * contract (same as `ListItemLink` / `ListItemButton`). Compose as a sibling of the row's primary
 * inside a `ListItem`, itself inside the `Collapsible.Root` that also wraps the nested `List` panel
 * — same shape as `ListSection`, just scoped to one row instead of a whole heading.
 */
export function ListItemDisclosureTrigger(props: ListItemDisclosureTriggerProps) {
  return (
    <BaseCollapsible.Trigger
      render={<CompositeItem tag="button" render={<ListItemDisclosureTriggerElement />} />}
      {...props}
    >
      <DisclosureIndicator motion="disclose" tint="secondary">
        <ChevronDownOutline />
      </DisclosureIndicator>
    </BaseCollapsible.Trigger>
  );
}
