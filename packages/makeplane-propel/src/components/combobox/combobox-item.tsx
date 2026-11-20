import { Combobox as BaseCombobox } from "@base-ui/react/combobox";
import type * as React from "react";

import {
  ComboboxCheckboxItemIndicator,
  ComboboxItem as ComboboxItemElement,
  ComboboxItemContent,
  ComboboxItemControl,
  ComboboxItemTitle,
  ComboboxItemTrailing,
  type ComboboxItemVariant,
} from "../../elements/combobox";
import { TickOutline } from "../../icons";
import { rendersContent } from "../../internal/renders-content";
import { ComboboxItemIndicator } from "./combobox-item-indicator";

export type { ComboboxItemVariant };

type ComboboxItemBaseProps = Omit<
  BaseCombobox.Item.Props,
  "children" | "className" | "label" | "style" | "value"
> & {
  /**
   * Row look. `neutral` is the standard text hierarchy, `accent` marks the primary action, and
   * `danger` marks a destructive one.
   *
   * @default "neutral"
   */
  variant?: ComboboxItemVariant;
  /**
   * Selection marker. `check` is the trailing accent check used by single-select; `checkbox` is the
   * leading checkbox box used by multi-select (the Figma dropdown row).
   *
   * @default "check"
   */
  selection?: "check" | "checkbox";
  /**
   * Leading element shown before the label, e.g. `<Icon icon={MapPin} tint="secondary" />`. On a
   * `selection="checkbox"` row it follows the checkbox box.
   */
  icon?: React.ReactNode;
  /** Content pinned at the row's inline end, e.g. a count. */
  trailing?: React.ReactNode;
};

type ComboboxItemPrimitiveValue = string | number | bigint | boolean | symbol;

function isPrimitiveValue(value: unknown): value is ComboboxItemPrimitiveValue {
  return (
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "bigint" ||
    typeof value === "boolean" ||
    typeof value === "symbol"
  );
}

export type ComboboxItemProps = ComboboxItemBaseProps &
  (
    | {
        /** Option value whose string form is used when `label` is omitted. */
        value: ComboboxItemPrimitiveValue;
        /** Option label. Defaults to the string form of `value`. */
        label?: string;
      }
    | {
        /** Option value. Object values cannot derive display text, so they require `label`. */
        value?: unknown;
        /** Visible option label. Required when `value` is not a primitive. */
        label: string;
      }
  );

/**
 * The ready-made option row: Base UI's `Item` behavior grafted onto the shared menu-row chrome so
 * the combobox list matches the dropdown panel. `selection="check"` reserves a TRAILING check
 * gutter (kept mounted while unselected); `selection="checkbox"` shows the LEADING checkbox box
 * used by multi-select.
 */
export function ComboboxItem({
  variant,
  selection = "check",
  icon,
  label,
  trailing,
  ...props
}: ComboboxItemProps) {
  const value = props.value;
  const resolvedLabel = label ?? (isPrimitiveValue(value) ? String(value) : "");
  return (
    <BaseCombobox.Item {...props} render={<ComboboxItemElement variant={variant} />}>
      {selection === "checkbox" ? (
        <ComboboxItemControl>
          <BaseCombobox.ItemIndicator keepMounted render={<ComboboxCheckboxItemIndicator />}>
            <TickOutline aria-hidden />
          </BaseCombobox.ItemIndicator>
        </ComboboxItemControl>
      ) : null}
      {icon}
      <ComboboxItemContent>
        <ComboboxItemTitle>{resolvedLabel}</ComboboxItemTitle>
      </ComboboxItemContent>
      {/* The single-select check trails the label instead of leading it, while the multi-select
          checkbox above keeps the leading slot — the two markers no longer share a column. It sits
          BEFORE `trailing` so the check stays adjacent to the label it marks and a shortcut/count
          keeps the row's outer edge. */}
      {selection === "check" ? <ComboboxItemIndicator /> : null}
      {rendersContent(trailing) ? <ComboboxItemTrailing>{trailing}</ComboboxItemTrailing> : null}
    </BaseCombobox.Item>
  );
}
