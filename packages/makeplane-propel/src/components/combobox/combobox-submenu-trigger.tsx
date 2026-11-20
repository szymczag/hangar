import { Combobox as BaseCombobox } from "@base-ui/react/combobox";
import type * as React from "react";

import {
  ComboboxItemContent,
  ComboboxItemTitle,
  ComboboxItemTrailing,
  ComboboxSubmenuTrigger as ComboboxSubmenuTriggerElement,
  type ComboboxSubmenuTriggerVariant,
} from "../../elements/combobox";
import { ChevronDownOutline } from "../../icons";
import { DisclosureIndicator } from "../../internal/disclosure-indicator";
import { rendersContent } from "../../internal/renders-content";
import { useComboboxSubmenuContext } from "./combobox-submenu-context";

export type ComboboxSubmenuTriggerProps = Omit<
  BaseCombobox.Item.Props,
  "children" | "className" | "label" | "style" | "render" | "value"
> & {
  /**
   * Row look. `neutral` is the standard text hierarchy, `accent` marks the primary action, and
   * `danger` marks a destructive one.
   *
   * @default "neutral"
   */
  variant?: ComboboxSubmenuTriggerVariant;
  /** Leading element shown before the label, e.g. `<Icon icon={Users} tint="secondary" />`. */
  icon?: React.ReactNode;
  /** Row label — the name of the nested list, not of a value. */
  label: string;
  /** Content pinned before the submenu chevron, e.g. a count. */
  trailing?: React.ReactNode;
};

/**
 * The parent row that opens a nested combobox. It is an option of the PARENT list — Base UI's
 * `Combobox.Item` behavior, so it keeps that list's highlight, arrow-key navigation and filtering —
 * but it carries **no value**: the pointer and `Enter` paths both suppress Base UI's own selection
 * (`preventBaseUIHandler`) and open the nested list instead. Only the nested list's items select.
 *
 * Pass it to `ComboboxSubmenu`'s `trigger` prop rather than rendering it as a child, so it resolves
 * against the parent combobox's context instead of the nested root's.
 *
 * It still registers with the parent list as an item, so a parent that derives its options from the
 * DOM rather than an `items` prop counts this row among them. Give such a parent an explicit
 * `items` list when that matters (a `ComboboxSelectAll`, for instance, should not count it).
 */
export function ComboboxSubmenuTrigger({
  variant,
  icon,
  label,
  trailing,
  ...props
}: ComboboxSubmenuTriggerProps) {
  const submenu = useComboboxSubmenuContext("ComboboxSubmenuTrigger");
  return (
    <BaseCombobox.Item
      {...props}
      ref={submenu.triggerRef}
      // The row is a way in, not a value, so it must not announce a selected state. Base UI sets
      // `aria-selected` from whether the item's value matches the root's — and an item with no
      // `value` is `null`, which MATCHES an unset single-select parent: every submenu row would
      // read as selected until the user picked something. `mergeProps` copies an explicit
      // `undefined` over Base UI's own value, which drops the attribute entirely.
      aria-selected={undefined}
      // Base UI sets `data-popup-open` on parts it owns the popup state for; this row's popup is
      // assembled by `ComboboxSubmenu`, so the attribute (and the open-row highlight keyed off it)
      // is set here. It stays a `data-*` hook and carries NO `aria-expanded`: ARIA does not allow
      // that attribute on `role="option"` (axe flags it), and a listbox option has no conforming
      // way to say it owns a nested listbox — that would be a `tree`. What a screen reader gets
      // instead is the nested list itself, which takes focus on open and announces its own name,
      // so give every `ComboboxSubmenuContent`'s list one (`aria-label`).
      data-popup-open={submenu.open ? "" : undefined}
      onClick={(event) => {
        // Suppresses `commitSelection` — the row is not a value. This one handler covers both the
        // pointer and the keyboard: Base UI dispatches a click on the highlighted item when `Enter`
        // is pressed while the parent's input or list has focus.
        event.preventBaseUIHandler();
        submenu.setOpen(true);
      }}
      onMouseUp={(event) => {
        // The other selection path: Base UI commits on mouseup when the press did NOT start on the
        // row (a drag out of the input and onto it).
        event.preventBaseUIHandler();
      }}
      onPointerEnter={submenu.scheduleOpen}
      onPointerLeave={submenu.scheduleClose}
      render={<ComboboxSubmenuTriggerElement variant={variant} />}
    >
      {icon}
      <ComboboxItemContent>
        <ComboboxItemTitle>{label}</ComboboxItemTitle>
      </ComboboxItemContent>
      {rendersContent(trailing) ? <ComboboxItemTrailing>{trailing}</ComboboxItemTrailing> : null}
      <DisclosureIndicator motion="pointEnd" tint="tertiary">
        <ChevronDownOutline />
      </DisclosureIndicator>
    </BaseCombobox.Item>
  );
}
