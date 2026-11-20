import { Accordion as BaseAccordion } from "@base-ui/react/accordion";
import type * as React from "react";

import {
  AccordionTrigger as AccordionTriggerElement,
  AccordionTriggerTitle,
} from "../../elements/accordion";
import { ChevronDownOutline } from "../../icons";
import { DisclosureIndicator } from "../../internal/disclosure-indicator";

export type AccordionTriggerProps = Omit<
  BaseAccordion.Trigger.Props,
  "children" | "className" | "style"
> & {
  /**
   * Element rendered before the label (inline-start), e.g. `<Icon icon={Folder} tint="secondary"
   * />`.
   */
  icon?: React.ReactNode;
  /** Visible trigger label. */
  label: string;
};

/**
 * The ready-made accordion trigger: grafts Base UI's trigger behavior onto the styled
 * `AccordionTrigger`, composing an optional `icon`, the `AccordionTriggerTitle`, and the
 * `DisclosureIndicator` chevron that rotates when the panel opens.
 */
export function AccordionTrigger({ icon, label, ...props }: AccordionTriggerProps) {
  return (
    <BaseAccordion.Trigger {...props} render={<AccordionTriggerElement />}>
      {icon}
      <AccordionTriggerTitle>{label}</AccordionTriggerTitle>
      <DisclosureIndicator motion="disclose" tint="secondary">
        <ChevronDownOutline />
      </DisclosureIndicator>
    </BaseAccordion.Trigger>
  );
}
