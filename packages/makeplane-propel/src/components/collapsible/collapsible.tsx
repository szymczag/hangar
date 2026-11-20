import { Collapsible as BaseCollapsible } from "@base-ui/react/collapsible";
import type * as React from "react";

import {
  Collapsible as CollapsibleElement,
  CollapsibleHeader,
  type CollapsibleHeaderProps,
  CollapsiblePanel,
  CollapsiblePanelContent,
  CollapsibleTrigger,
  CollapsibleTriggerTitle,
  CollapsibleTriggerTrailing,
} from "../../elements/collapsible";
import { ChevronDownOutline } from "../../icons";
import { DisclosureIndicator } from "../../internal/disclosure-indicator";

export type CollapsibleProps = Omit<
  BaseCollapsible.Root.Props,
  "className" | "style" | "render"
> & {
  /**
   * Element to graft the styled frame onto instead of the default `div` — element form only, the
   * callback form's `state` isn't wired through the styled frame.
   */
  render?: React.ReactElement;
  /**
   * Element rendered before the label (inline-start), e.g. `<Icon icon={Folder} tint="secondary"
   * size="inherit" />`.
   */
  icon?: React.ReactNode;
  /** The button content that opens and closes the panel. */
  trigger: React.ReactNode;
  /**
   * Control rendered at the header's inline-end, as a sibling of the trigger — never inside it (the
   * trigger is a button; nested buttons are invalid). Typical content is an `IconButton`.
   * Independent of open state: clicking it does not toggle the panel. Root `disabled` does not
   * disable this control.
   */
  trailing?: React.ReactNode;
  /**
   * Sidebar placement uses compact insets, an unpadded body, and an independent action before the
   * end-aligned indicator. Inline placement keeps the label and indicator together.
   *
   * @default "inline"
   */
  placement?: CollapsibleHeaderProps["placement"];
  /** The collapsible content region. */
  children: React.ReactNode;
  /**
   * Whether to show the rotating chevron indicator after the trigger label.
   *
   * @default true
   */
  indicator?: boolean;
  /** Keep the panel in the DOM while closed — Base UI's `Panel.keepMounted`. */
  keepMounted?: boolean;
  /** Reveal on the browser's find-in-page — Base UI's `Panel.hiddenUntilFound`. */
  hiddenUntilFound?: boolean;
  /**
   * Drop the content region's own padding, for content that brings its own spacing. Independent of
   * `placement` — `placement="sidebar"` already defaults to unpadded content; `hug` lets `inline`
   * (or a future placement) opt into the same look without switching placement.
   *
   * @default false
   */
  hug?: boolean;
};

/**
 * The ready-made collapsible: a single show/hide disclosure that wires the trigger and panel for
 * the 90% case. Pass `trigger` for the toggle button label and `children` for the body; optional
 * `icon` for a leading glyph and `trailing` for a header-end control (sibling of the trigger).
 * Forward `defaultOpen` (uncontrolled) or `open` + `onOpenChange` (controlled) to drive it. Set
 * `indicator={false}` to omit the rotating chevron from the trigger.
 */
export function Collapsible({
  icon,
  trigger,
  trailing,
  children,
  indicator = true,
  placement = "inline",
  keepMounted,
  hiddenUntilFound,
  hug = false,
  render,
  ...props
}: CollapsibleProps) {
  return (
    // Consumer `render` threads into the styled frame (behavior outer, styled part as the render
    // target, rule 1a) rather than replacing it.
    <BaseCollapsible.Root {...props} render={<CollapsibleElement render={render} />}>
      <CollapsibleHeader placement={placement}>
        <BaseCollapsible.Trigger render={<CollapsibleTrigger placement={placement} />}>
          {placement === "inline" ? icon : null}
          <CollapsibleTriggerTitle placement={placement}>
            {placement === "sidebar" ? icon : null}
            {trigger}
          </CollapsibleTriggerTitle>
          {indicator ? (
            <DisclosureIndicator motion="disclose" tint="secondary">
              <ChevronDownOutline />
            </DisclosureIndicator>
          ) : null}
        </BaseCollapsible.Trigger>
        {trailing ? (
          <CollapsibleTriggerTrailing placement={placement}>{trailing}</CollapsibleTriggerTrailing>
        ) : null}
      </CollapsibleHeader>
      <BaseCollapsible.Panel
        keepMounted={keepMounted}
        hiddenUntilFound={hiddenUntilFound}
        render={<CollapsiblePanel />}
      >
        <CollapsiblePanelContent placement={placement} hug={hug}>
          {children}
        </CollapsiblePanelContent>
      </BaseCollapsible.Panel>
    </BaseCollapsible.Root>
  );
}
