import { Select as BaseSelect } from "@base-ui/react/select";
import * as React from "react";

import {
  SelectCheckboxItemIndicator,
  SelectItem as SelectItemElement,
  SelectItemContent,
  SelectItemDescription,
  SelectItemIndicator,
  SelectItemSecondaryText,
  SelectItemText,
  SelectItemTitleRow,
  SelectItemTrailing,
} from "../../elements/select";
import { TickOutline } from "../../icons";
import { rendersContent } from "../../internal/renders-content";
import { SelectMultipleContext } from "./select-multiple-context";

type SelectItemBaseProps = Omit<
  BaseSelect.Item.Props,
  "children" | "className" | "label" | "render" | "style" | "value"
> & {
  /**
   * No longer has any effect: option rows are one fixed height, whatever the trigger's size. Still
   * accepted so existing call sites keep compiling — drop it.
   *
   * @deprecated Option rows no longer take a size.
   * @default "lg"
   */
  size?: "md" | "lg" | "xl" | "2xl";
  /**
   * Leading element shown before the label, e.g. `<Icon icon={Server} tint="secondary" />`. In a
   * `multiple` select it follows the checkbox box.
   */
  icon?: React.ReactNode;
  /** Muted secondary line under the label. The row grows to fit it. */
  description?: string;
  /** Muted text shown inline after the label. */
  secondaryText?: string;
  /** Content pinned at the row's inline end, after the check, e.g. a count (`12`) or a `<Badge />`. */
  trailing?: React.ReactNode;
};

type SelectItemPrimitiveValue = string | number | bigint | boolean | symbol;

function isPrimitiveValue(value: unknown): value is SelectItemPrimitiveValue {
  return (
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "bigint" ||
    typeof value === "boolean" ||
    typeof value === "symbol"
  );
}

export type SelectItemProps = SelectItemBaseProps &
  (
    | {
        /** Option value whose string form is used when `label` is omitted. */
        value: SelectItemPrimitiveValue;
        /** Option label. Defaults to the string form of `value`. */
        label?: string;
      }
    | {
        /** Option value. Object values cannot derive display text, so they require `label`. */
        value?: unknown;
        /** Visible option and typeahead label. Required when `value` is not a primitive. */
        label: string;
      }
  );

/**
 * The ready-made select option row: grafts Base UI's `Select.Item` behavior onto the styled
 * `SelectItem` row — the shared menu-row chrome, so the list matches Combobox and Menu — and lays
 * out an optional leading icon, the label with any inline secondary text, an optional description
 * line, the selection marker, and trailing content. A single-select row trails its label with a
 * check (`SelectItemIndicator`); inside a `multiple` select the row leads with a checkbox box
 * (`SelectCheckboxItemIndicator`), matching a multi-select Combobox. Both markers are
 * `keepMounted`: the check so its gutter holds while unselected (a selection change never
 * re-truncates a label), the checkbox so the empty box shows. Only the `label` goes through Base
 * UI's `Select.ItemText`, so it alone is what the trigger shows for the selected option.
 */
export function SelectItem({
  icon,
  label,
  description,
  secondaryText,
  trailing,
  size: _size,
  ...props
}: SelectItemProps) {
  const multiple = React.useContext(SelectMultipleContext);
  const value = props.value;
  const resolvedLabel = label ?? (isPrimitiveValue(value) ? String(value) : "");
  // The taller, top-aligned row layout is implied by having a description — derived, not a prop.
  const layout = description ? "stacked" : "single";
  return (
    // `label` also goes to Base UI as the typeahead text, so typing matches the label alone rather
    // than the row's whole text (secondary text, description, trailing).
    <BaseSelect.Item
      {...props}
      label={resolvedLabel}
      render={<SelectItemElement layout={layout} />}
    >
      {multiple ? (
        <BaseSelect.ItemIndicator keepMounted render={<SelectCheckboxItemIndicator />}>
          <TickOutline aria-hidden />
        </BaseSelect.ItemIndicator>
      ) : null}
      {icon}
      <SelectItemContent>
        <SelectItemTitleRow>
          <BaseSelect.ItemText render={<SelectItemText />}>{resolvedLabel}</BaseSelect.ItemText>
          {secondaryText ? (
            <SelectItemSecondaryText>{secondaryText}</SelectItemSecondaryText>
          ) : null}
        </SelectItemTitleRow>
        {description ? <SelectItemDescription>{description}</SelectItemDescription> : null}
      </SelectItemContent>
      {/* The check sits BEFORE `trailing`, so it stays next to the label it marks and a count or
          badge keeps the row's outer edge — the same order as Combobox and Menu. */}
      {multiple ? null : (
        <BaseSelect.ItemIndicator keepMounted render={<SelectItemIndicator />}>
          <TickOutline aria-hidden />
        </BaseSelect.ItemIndicator>
      )}
      {rendersContent(trailing) ? <SelectItemTrailing>{trailing}</SelectItemTrailing> : null}
    </BaseSelect.Item>
  );
}
