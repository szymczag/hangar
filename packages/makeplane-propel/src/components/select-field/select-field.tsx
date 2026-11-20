import { Select as BaseSelect } from "@base-ui/react/select";
import * as React from "react";

import { FieldControlContent } from "../../elements/field/field-control-content";
import { FieldLabelGroup } from "../../elements/field/field-label-group";
import { Field, FieldDescription, FieldLabel } from "../field";
import { FieldHelperText } from "../field/field-helper-text";
import {
  Select,
  SelectContent,
  type SelectContentProps,
  SelectGroup,
  SelectGroupLabel,
  type SelectGroupLabelProps,
  SelectItem,
  type SelectItemProps,
  SelectList,
  type SelectProps,
  SelectSeparator,
  SelectTrigger,
  type SelectTriggerProps,
  type SelectTriggerVariantProps,
} from "../select";

export type {
  SelectTriggerAnySize,
  SelectTriggerFieldSize,
  SelectTriggerPillSize,
  SelectTriggerSize,
  SelectTriggerVariant,
  SelectTriggerWidth,
} from "../select";

/**
 * One option in the popup. Takes every `SelectItem` prop — `label`, `icon`, `description`,
 * `secondaryText`, `trailing`, `disabled`, … — so a prop `SelectItem` gains reaches the field
 * without a change here. `value` is what the option selects: a string by default, or any type the
 * field is given (`SelectField<Value>`). An omitted label falls back to `itemToStringLabel`, then
 * to a primitive value's string form.
 */
export type SelectFieldOption<Value = string> = Omit<
  SelectItemProps,
  "label" | "size" | "value"
> & {
  /** The value the option selects. */
  value: Value;
  /** Option label. Defaults to a primitive value or the field's `itemToStringLabel` result. */
  label?: string;
};

/** A labeled group of options. Takes the `SelectGroupLabel` heading's `meta`. */
export type SelectFieldGroup<Value = string> = Pick<SelectGroupLabelProps, "meta"> & {
  /** Identifies the group among the field's entries, so it must be unique within `options`. */
  key: string;
  /** The group's heading. */
  label: string;
  /** The group's options. */
  options: readonly SelectFieldOption<Value>[];
};

/**
 * One entry in `SelectField`'s `options`: an option, a group of options, or `"separator"` — a
 * divider drawn exactly where it sits in the list.
 */
export type SelectFieldEntry<Value = string> =
  | SelectFieldOption<Value>
  | SelectFieldGroup<Value>
  | "separator";

/**
 * The trigger's `icon`, `placeholder` and `variant` and the popup's `sizing`, `header` and `footer`
 * come straight from `SelectTrigger` and `SelectContent`, so they stay in step with the parts.
 */
type SelectFieldBaseProps<Value = string, Multiple extends boolean | undefined = false> = Omit<
  SelectProps<Value, Multiple>,
  "children" | "items"
> &
  Pick<SelectTriggerProps, "icon" | "placeholder"> &
  Pick<SelectContentProps, "sizing" | "header" | "footer"> & {
    /**
     * Supporting text shown below the label, above the trigger. Always shown, alongside
     * `hint`/`error`.
     */
    description?: React.ReactNode;
    /** Error text shown below the control. */
    error?: React.ReactNode;
    /** Helper text shown below the control. Replaced by `error` when an error is set. */
    hint?: React.ReactNode;
    /** Marks the field required and adds a `*` asterisk when a visible `label` is present. */
    required?: boolean;
    /**
     * Options rendered in the popup. An entry with its own `options` and no `value` is a group,
     * rendered under its `label` heading. A `"separator"` entry draws a divider exactly where it
     * sits — between groups, between plain options, or both; nothing is added automatically. A
     * group with no options, a separator at either end of the list, or one right after another is
     * skipped, so conditionally built lists never show a bare heading or a stray line. Every option
     * mounts when the popup opens; Select is not windowed. Use ComboboxField for large catalogs,
     * searchable choices or accumulated server pages.
     */
    options: readonly SelectFieldEntry<Value>[];
  };

/** A field needs either a visible label or an accessible-only label on its trigger. */
type SelectFieldLabelProps =
  | { label: string; "aria-label"?: string }
  | { label?: undefined; "aria-label": string };

export type SelectFieldProps<
  Value = string,
  Multiple extends boolean | undefined = false,
> = SelectFieldBaseProps<Value, Multiple> & SelectTriggerVariantProps & SelectFieldLabelProps;

// An option always has a `value` and a group never does, so an option that happens to carry an
// `options` field is still an option.
function isGroup<Value>(
  entry: Exclude<SelectFieldEntry<Value>, "separator">,
): entry is SelectFieldGroup<Value> {
  return !("value" in entry) && Array.isArray(entry.options);
}

/** Ready-to-use select field with label, trigger, popup options, and helper/error text. */
export function SelectField<Value = string, Multiple extends boolean | undefined = false>({
  description,
  disabled,
  error,
  hint,
  icon,
  label,
  "aria-label": ariaLabel,
  placeholder,
  required,
  size,
  variant,
  width,
  name,
  options,
  sizing,
  header,
  footer,
  itemToStringLabel: providedItemToStringLabel,
  itemToStringValue,
  isItemEqualToValue,
  ...selectProps
}: SelectFieldProps<Value, Multiple>) {
  // Pill's xs/sm typography belongs to the trigger only; the surrounding field copy stays on its
  // smallest established rung instead of extending compact chip sizes across every Field part.
  const fieldSize = variant === "pill" ? "md" : size;
  const resolveOptionLabel = React.useCallback(
    (value: Value, optionLabel?: string) =>
      optionLabel ??
      providedItemToStringLabel?.(value) ??
      (value == null || typeof value === "object" ? "" : String(value)),
    [providedItemToStringLabel],
  );
  // Memoized on `options` and `isItemEqualToValue`, since Base UI keeps `items` and
  // `itemToStringLabel` in an effect's dependencies. Pass stable references to avoid re-syncing its
  // store on every render.
  const { entries, items, defaultItemToStringLabel } = React.useMemo(() => {
    // Drop empty groups first, so a group filtered down to nothing leaves no bare heading and the
    // separators around it are tidied below.
    const visible = options.filter(
      (entry) => entry === "separator" || !isGroup(entry) || entry.options.length > 0,
    );
    // Skip the separators that would draw a stray line: at either end of the list, or right after
    // another separator.
    const lastOptionIndex = visible.findLastIndex((entry) => entry !== "separator");
    const entries = visible.filter(
      (entry, index) =>
        entry !== "separator" ||
        (index > 0 && index < lastOptionIndex && visible[index - 1] !== "separator"),
    );
    // Base UI looks the trigger's label up in `items`, so it gets every option — grouped or not —
    // flattened to its `{ label, value }` pair.
    const items = entries
      .flatMap((entry) => (entry === "separator" ? [] : isGroup(entry) ? entry.options : [entry]))
      .map((option) => ({
        label: resolveOptionLabel(option.value, option.label),
        value: option.value,
      }));
    // Base UI only finds an item's label by value when the value is a primitive; an object value
    // would show as JSON. Look every value up here instead, with the field's own comparer.
    const isEqual = isItemEqualToValue ?? Object.is;
    const defaultItemToStringLabel = (value: Value) =>
      items.find((item) => item.value != null && isEqual(item.value, value))?.label ??
      (typeof value === "object" ? "" : String(value));
    return { entries, items, defaultItemToStringLabel };
  }, [options, isItemEqualToValue, resolveOptionLabel]);
  // A primitive value is its own key; an object value needs `itemToStringValue` (the same string
  // Base UI submits), and falls back to its position when that is not given.
  const keyOf = (value: Value, index: number) =>
    (value != null ? itemToStringValue?.(value) : undefined) ??
    (typeof value === "object" && value !== null ? index : String(value));
  const renderOption = ({ value, label, ...option }: SelectFieldOption<Value>, index: number) => (
    <SelectItem
      key={`option:${keyOf(value, index)}`}
      value={value}
      label={resolveOptionLabel(value, label)}
      {...option}
    />
  );
  return (
    <Field name={name} size={fieldSize} disabled={disabled} invalid={error != null || undefined}>
      <Select
        disabled={disabled}
        items={items}
        itemToStringLabel={providedItemToStringLabel ?? defaultItemToStringLabel}
        itemToStringValue={itemToStringValue}
        isItemEqualToValue={isItemEqualToValue}
        required={required}
        {...selectProps}
      >
        {/* Graft Base UI's select-label association onto the shared, size-scaled `FieldLabel`
            (md=body-xs) so the label matches the other field wrappers (input/combobox/autocomplete)
            — the picker's own fixed-14px `SelectLabel` rendered it a step too large. Elements
            `FieldLabelGroup` (not the ready-made helper) keeps that graft and the tighter
            title→description gap. */}
        {label != null || description != null ? (
          <FieldLabelGroup orientation="vertical">
            {label != null ? (
              <BaseSelect.Label
                render={<FieldLabel size={fieldSize} inset={false} required={required} />}
              >
                {label}
              </BaseSelect.Label>
            ) : null}
            {description != null ? (
              <FieldDescription size={fieldSize}>{description}</FieldDescription>
            ) : null}
          </FieldLabelGroup>
        ) : null}
        <FieldControlContent orientation="vertical" size={fieldSize}>
          {variant === "pill" ? (
            <SelectTrigger
              size={size}
              variant="pill"
              icon={icon}
              placeholder={placeholder}
              aria-label={ariaLabel}
            />
          ) : (
            <SelectTrigger
              size={size}
              variant={variant}
              width={width}
              icon={icon}
              placeholder={placeholder}
              aria-label={ariaLabel}
            />
          )}
          <SelectContent
            sizing={sizing ?? (variant === "pill" ? "auto" : "anchor")}
            header={header}
            footer={footer}
          >
            <SelectList>
              {/* Figma's popup rows stay a fixed size across every trigger size — only the
                  trigger/label/helper text scale with `size`. */}
              {entries.map((entry, index) => {
                if (entry === "separator") return <SelectSeparator key={`separator:${index}`} />;
                if (isGroup(entry)) {
                  return (
                    <SelectGroup key={`group:${entry.key}`}>
                      <SelectGroupLabel meta={entry.meta}>{entry.label}</SelectGroupLabel>
                      {entry.options.map(renderOption)}
                    </SelectGroup>
                  );
                }
                return renderOption(entry, index);
              })}
            </SelectList>
          </SelectContent>
          <FieldHelperText size={fieldSize} hint={hint} error={error} />
        </FieldControlContent>
      </Select>
    </Field>
  );
}
