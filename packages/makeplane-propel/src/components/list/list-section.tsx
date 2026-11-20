import { Collapsible as BaseCollapsible } from "@base-ui/react/collapsible";
import type * as React from "react";

import { CollapsiblePanel, Collapsible as CollapsibleElement } from "../../elements/collapsible";
import { ListSectionPanelContent, ListSectionTrigger } from "../../elements/list";
import { ChevronDownOutline } from "../../icons";
import { DisclosureIndicator } from "../../internal/disclosure-indicator";

export type ListSectionProps = Omit<
  BaseCollapsible.Root.Props,
  "className" | "style" | "render"
> & {
  /** The section heading shown in the toggle. */
  label: string;
  /** The section body — typically a `List` of rows. */
  children: React.ReactNode;
  /**
   * Whether to show the rotating disclosure chevron at the heading's inline-end.
   *
   * @default true
   */
  indicator?: boolean;
  /**
   * Element to graft the styled frame onto instead of the default `div` — element form only, the
   * callback form's `state` isn't wired through the styled frame.
   */
  render?: React.ReactElement;
};

/**
 * A ready-made collapsible list section: a muted heading that toggles its body, with the disclosure
 * chevron (points inline-end while collapsed, rotates down when open). Pass `label` for the heading
 * and `children` for the body (typically a `List` of rows); forward `defaultOpen` (uncontrolled) or
 * `open` + `onOpenChange` (controlled) to drive it. Set `indicator={false}` to omit the chevron.
 *
 * Children sit in `ListSectionPanelContent` (heading-to-row gap only) inside the height-animating
 * panel — list rows own their own horizontal padding, so this does not wrap
 * `CollapsiblePanelContent` (that part carries Collapsible's Figma panel inset + prose).
 */
export function ListSection({
  label,
  children,
  indicator = true,
  render,
  ...props
}: ListSectionProps) {
  return (
    // Consumer `render` threads into the styled frame (behavior outer, styled part as the render
    // target, rule 1a) rather than replacing it.
    <BaseCollapsible.Root {...props} render={<CollapsibleElement render={render} />}>
      <BaseCollapsible.Trigger render={<ListSectionTrigger />}>
        {label}
        {indicator ? (
          <DisclosureIndicator motion="disclose" tint="secondary">
            <ChevronDownOutline />
          </DisclosureIndicator>
        ) : null}
      </BaseCollapsible.Trigger>
      <BaseCollapsible.Panel render={<CollapsiblePanel />}>
        <ListSectionPanelContent>{children}</ListSectionPanelContent>
      </BaseCollapsible.Panel>
    </BaseCollapsible.Root>
  );
}
