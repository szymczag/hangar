import { Combobox as BaseCombobox } from "@base-ui/react/combobox";
import { defaultRangeExtractor, useVirtualizer, type Range } from "@tanstack/react-virtual";
import * as React from "react";

import { ComboboxItemPositioner, ComboboxListSpacer } from "../../elements/combobox";
import { FieldControlContent } from "../../elements/field/field-control-content";
import { FieldLabel } from "../../elements/field/field-label";
import { FieldLabelGroup } from "../../elements/field/field-label-group";
import { FieldLabelRequiredMarker } from "../../elements/field/field-label-required-marker";
import type { FieldSize } from "../../elements/field/variants";
import { useControllableState } from "../../hooks/use-controllable-state";
import { defaultComboboxOverflowLabel } from "../../internal/combobox-overflow-label";
import { createSelectionMatcher } from "../../internal/selection-membership";
import {
  Combobox,
  ComboboxContent,
  type ComboboxContentProps,
  ComboboxEmpty,
  ComboboxItem,
  type ComboboxItemProps,
  ComboboxList,
  type ComboboxProps,
  ComboboxSearch,
  ComboboxSelectAll,
  ComboboxSeparator,
  ComboboxStickyList,
  ComboboxTrigger,
  type ComboboxTriggerProps,
  type ComboboxTriggerVariantProps,
} from "../combobox";
import { Field } from "../field";
import { FieldDescription } from "../field/field-description";
import { FieldHelperText } from "../field/field-helper-text";

export type {
  ComboboxTriggerPillSize,
  ComboboxTriggerVariant,
  ComboboxTriggerWidth,
  ComboboxVariant,
} from "../combobox";
export type { FieldSize };

/**
 * Per-row props from `getItemProps`: any `ComboboxItem` prop — `icon`, `trailing`, `disabled`,
 * `variant`, … — except the ones the field owns (`value`, `label`, `selection`, `index`).
 */
export type ComboboxFieldItemProps = Omit<
  ComboboxItemProps,
  "value" | "label" | "selection" | "index"
>;

/** The field's options, and optionally the caller-filtered subset on offer. */
type ComboboxFieldOptions<Value extends string | number, Item> = {
  /**
   * Known flat options: primitive IDs, or records with explicit value/label accessors. Selected
   * values are always IDs. Keep off-page selected records here to resolve their labels, or supply
   * `itemToStringLabel(id)` as a fallback. Records must not have an array-valued `items` property
   * (reserved for Base UI groups). This field does not fetch or retain past records.
   */
  items: readonly Item[] &
    NoInfer<NonNullable<Parameters<typeof BaseCombobox.createItems<Item, Value>>[0]>>;
  /**
   * Externally filtered flat options offered in the popup. When supplied, bulk actions affect only
   * these records, not all known `items`. Pass [] for an empty response. Omit for local filtering;
   * local search does not change the bulk-action scope. Fetching and pagination are caller-owned.
   */
  filteredItems?: readonly Item[];
};

/**
 * Single-line option row height (`menuRowSingleHeightClass` = `h-8`). Virtualizer estimates and
 * popup list insets must stay in lockstep with the rendered row chrome.
 */
const MENU_ROW_SINGLE_HEIGHT_PX = 32;
/** Flat popup list inset (`p-1`); subtracted from virtual row offsets and used as scroll padding. */
const COMBOBOX_LIST_INSET_PX = 4;

/** One selected value, or several. Mirrors the `Combobox` root's `multiple`. */
type ComboboxFieldSelection<Value extends string | number> =
  | {
      /**
       * Allow several selections: checkbox rows, a Select all row, and a trigger that previews the
       * first `maxVisible` labels. Off (the default) picks one value, with check rows, and closes
       * the popup on pick. Fixed for a mounted field: the value's shape follows it, so switching
       * modes means remounting the field (e.g. with a new `key`).
       *
       * @default false
       */
      multiple: true;
      /** The selected values (controlled). */
      value?: Value[] | null;
      /** The initially selected values (uncontrolled). */
      defaultValue?: Value[] | null;
      /**
       * Called when the selection changes. Item presses pass Base UI's event `details`; Select all
       * passes only the next value.
       */
      onValueChange?: (
        value: Value[],
        details?: Parameters<NonNullable<ComboboxProps<Value, true>["onValueChange"]>>[1],
      ) => void;
      /**
       * Maximum selected labels to preview. A nonnegative integer; zero shows only the count.
       * Hidden labels are not formatted. Long previews truncate without hiding the overflow count.
       *
       * @default 3
       */
      maxVisible?: number;
      /**
       * Non-interactive summary of selections beyond `maxVisible`. Receives the hidden count and
       * how many labels remain in the preview. Override to localize.
       *
       * @default (hiddenCount, { visibleCount }) => visibleCount > 0 ? `+${hiddenCount} more` : `${hiddenCount} selected`
       */
      overflowLabel?: (hiddenCount: number, details: { visibleCount: number }) => React.ReactNode;
      /**
       * Label for the sticky row that selects or clears every item.
       *
       * Acts on the whole `items` list, NOT on whatever the panel search has filtered down to — so
       * pressing it while a query is active also selects the values the query hid, and the row's
       * checked / indeterminate state likewise reflects `items` rather than the visible subset.
       * When `filteredItems` is supplied it defines the offered list instead. Other selections are
       * preserved when selecting or clearing this list. This does not select unseen server results;
       * use a label such as "Select loaded members" for remote pages.
       *
       * @default "Select all"
       */
      selectAllLabel?: string;
    }
  | {
      multiple?: false;
      /** The selected value (controlled); `null` for none. */
      value?: Value | null;
      /** The initially selected value (uncontrolled). */
      defaultValue?: Value | null;
      /** Called when the selection changes, with Base UI's event `details`. */
      onValueChange?: (
        value: Value | null,
        details: Parameters<NonNullable<ComboboxProps<Value, false>["onValueChange"]>>[1],
      ) => void;
      maxVisible?: never;
      overflowLabel?: never;
      selectAllLabel?: never;
    };

/** A field needs either a visible label or an accessible-only label on its trigger. */
type ComboboxFieldLabelProps =
  | { label: string; "aria-label"?: string }
  | { label?: undefined; "aria-label": string };

/**
 * The trigger's `icon`, `trailing` and `placeholder`, its `variant`/`size` pairing, and the popup's
 * `footer` and `sizing` come straight from `ComboboxTrigger` and `ComboboxContent`, so they stay in
 * step with the parts.
 */
type ComboboxFieldSharedProps<Value extends string | number, Item> = Omit<
  ComboboxProps<Value, true, Item>,
  | "children"
  | "items"
  | "filteredItems"
  | "multiple"
  | "value"
  | "defaultValue"
  | "onValueChange"
  | "virtualized"
  | "isItemEqualToValue"
> &
  Pick<ComboboxTriggerProps, "icon" | "trailing" | "placeholder"> &
  Pick<ComboboxContentProps, "footer"> &
  ComboboxTriggerVariantProps &
  ComboboxFieldOptions<Value, Item> &
  ComboboxFieldSelection<Value> & {
    /**
     * Mount only visible options and a small buffer. The popup stays at the anchor width and caps
     * at 288px tall (`sizing="anchor-fixed"`) so a mid-open height settle cannot shrink under the
     * virtualizer. Set false only when every option must remain mounted; rendering then grows with
     * the list and the popup uses available height.
     *
     * @default true
     */
    virtualized?: boolean;
    /**
     * How the popup takes its width (see `ComboboxContent`). Defaults to `anchor-fixed` for a
     * virtualized list and `anchor` otherwise. A `pill` trigger defaults to the content's width
     * instead (`auto-fixed` virtualized, `auto` otherwise), so the options are not squeezed to its
     * compact width.
     */
    sizing?: ComboboxContentProps["sizing"];
    /** Supporting text shown below the label. */
    description?: React.ReactNode;
    /**
     * Extra `ComboboxItem` props for an option's row, e.g. `{ icon, trailing, disabled }`. The
     * field sets each row's `value`, `label` and selection marker itself. Select all skips a
     * `disabled` row: it neither selects nor clears it. That scope calls this for every offered
     * option, so keep it referentially stable for large lists.
     */
    getItemProps?: (item: Item) => ComboboxFieldItemProps;
    /** Message rendered when no item matches. */
    empty: React.ReactNode;
    /** Error text shown below the control. */
    error?: React.ReactNode;
    /** Helper text shown below the control. Replaced by `error` when an error is set. */
    hint?: React.ReactNode;
    /**
     * Accessible name and placeholder for the panel search field.
     *
     * @default "Search"
     */
    searchLabel?: string;
  } & ComboboxFieldLabelProps;

/**
 * Primitive options (string/number lists). Accessors are optional — each item is its own ID and
 * default label. Prefer stable `getItemValue` / `getItemLabel` references for large lists; when an
 * accessor's return values change, pass a new `items` array so caches invalidate.
 */
export type ComboboxFieldProps<Value extends string | number = string> = ComboboxFieldSharedProps<
  Value,
  Value
> & {
  /** Derive a stable unique ID. Primitive options use themselves when omitted. */
  getItemValue?: (item: Value) => Value;
  /** Derive the display/filter label. Defaults to `itemToStringLabel`, then `String`. */
  getItemLabel?: (item: Value) => string;
};

/**
 * Record options. Both accessors are required: selection is ID-based, labels may repeat. Prefer
 * stable accessor references for large lists; when an accessor's return values change, pass a new
 * `items` array so caches invalidate.
 */
export type ComboboxFieldRecordProps<
  Value extends string | number,
  Item extends object,
> = ComboboxFieldSharedProps<Value, Item> & {
  /**
   * Required for record items: derive a stable unique ID. Omit for string/number items, which are
   * their own IDs.
   */
  getItemValue: (item: Item) => Value;
  /**
   * Required for record items: derive the display/filter label (labels may repeat). Omit for
   * string/number items, which use `itemToStringLabel` or `String`.
   */
  getItemLabel: (item: Item) => string;
};

type ComboboxFieldImplProps<Value extends string | number, Item> = ComboboxFieldSharedProps<
  Value,
  Item
> & {
  getItemValue?: (item: Item) => Value;
  getItemLabel?: (item: Item) => string;
};

/**
 * Ready-to-use combobox field: a closed trigger, overlay search, option rows, and helper/error
 * text. Picks one value by default; `multiple` picks several, with checkbox rows and Select all.
 *
 * Record options require `getItemValue` and `getItemLabel`. Primitive string/number options use
 * themselves as IDs when those accessors are omitted. For large lists, keep accessors and
 * `itemToStringLabel` referentially stable; supply a new `items` array when what they return for an
 * item changes.
 */
export function ComboboxField<Value extends string | number, Item extends object>(
  props: ComboboxFieldRecordProps<Value, Item>,
): React.JSX.Element;
export function ComboboxField<Value extends string | number>(
  props: ComboboxFieldProps<Value>,
): React.JSX.Element;
export function ComboboxField<Value extends string | number = string, Item = Value>({
  variant,
  width,
  description,
  trailing,
  icon,
  disabled,
  empty,
  error,
  hint,
  items,
  filteredItems,
  getItemValue,
  getItemLabel,
  label,
  "aria-label": ariaLabel,
  size,
  name,
  placeholder,
  multiple = false,
  maxVisible = 3,
  overflowLabel = defaultComboboxOverflowLabel,
  required,
  searchLabel = "Search",
  selectAllLabel = "Select all",
  value,
  defaultValue,
  onValueChange,
  virtualized = true,
  sizing,
  footer,
  getItemProps,
  onItemHighlighted,
  onInputValueChange,
  ...comboboxProps
}: ComboboxFieldImplProps<Value, Item>) {
  // Pill's compact sizes belong to the trigger only; the surrounding field copy stays on its
  // smallest established rung, as in `SelectField`.
  const fieldSize = variant === "pill" ? "md" : size;
  const hasCompactTrigger = variant === "pill" || width === "fit";
  const display = comboboxProps.itemToStringLabel ?? String;
  // Without an accessor the public type permits only primitive values as items.
  const valueOf = React.useCallback(
    (item: Item): Value => {
      if (getItemValue) return getItemValue(item);
      if (isOptionValue<Value>(item)) return item;
      throw new Error("ComboboxField item is not a primitive value; pass getItemValue");
    },
    [getItemValue],
  );
  // Record labels come from `getItemLabel` alone, so an inline `itemToStringLabel` does not rebuild
  // the collection.
  const primitiveLabel = getItemLabel ? undefined : display;
  const labelOf = React.useMemo(
    () => getItemLabel ?? ((item: Item) => (primitiveLabel ?? String)(valueOf(item))),
    [getItemLabel, primitiveLabel, valueOf],
  );
  const keyOf = React.useCallback((item: Item) => itemKey(valueOf(item)), [valueOf]);
  const collection = React.useMemo(
    () =>
      getItemValue || getItemLabel
        ? BaseCombobox.createItems<Item, Value>(
            // Props already reject group-shaped items; NoInfer on the public type is for inference.
            // createItems' first arg is invariant in Item and does not accept Item[] directly.
            // Props already reject group-shaped items; NoInfer on the public type is for inference.
            // createItems' first arg is invariant in Item and does not accept Item[] directly.
            items as Parameters<typeof BaseCombobox.createItems<Item, Value>>[0],
            { getValue: valueOf, getLabel: labelOf },
          )
        : items,
    [items, getItemValue, getItemLabel, valueOf, labelOf],
  );
  // Select all acts on the offered options a user could pick themselves: a row `getItemProps`
  // disables is neither selected nor cleared by it.
  const offeredValues = React.useMemo(() => {
    const offered = filteredItems ?? items;
    if (!getItemProps) return offered.map(valueOf);
    const values: Value[] = [];
    for (const item of offered) if (!getItemProps(item).disabled) values.push(valueOf(item));
    return values;
  }, [filteredItems, items, valueOf, getItemProps]);
  // Name the trigger via `htmlFor` (not `Field.Label`) so panel Search isn't called `{label}`. A
  // visible label also names the overlay dialog; an accessible-only field passes its name directly.
  const labelId = React.useId();
  const triggerId = React.useId();
  const [viewport, setViewport] = React.useState<HTMLDivElement | null>(null);
  const [highlight, setHighlight] = React.useState({ index: -1, scroll: false });
  // Virtualized lists own scroll reset on filter; Base UI skips its own when `virtualized` is set.
  const [queryEpoch, bumpQueryEpoch] = React.useReducer((n: number) => n + 1, 0);

  // The selection is always an array here — one entry at most without `multiple` — so the preview,
  // Select all and the rows share one path. Values are primitives, so an array is always a list.
  const [selectedValues, setSelected] = useControllableState<Value[]>({
    value: value === undefined ? undefined : toSelection(value),
    defaultValue: toSelection(defaultValue),
  });
  // The consumer's callback takes an array with `multiple` and one value (or null) without.
  const emitValueChange = onValueChange as
    | ((next: Value[] | Value | null, details?: ComboboxValueChangeDetails<Value>) => void)
    | undefined;
  const selectValues = (next: Value[], details?: ComboboxValueChangeDetails<Value>) => {
    setSelected(next);
    const emitted = multiple ? next : (next[0] ?? null);
    // Select all has no Base UI event, so it passes the value alone (no trailing `undefined`).
    if (details === undefined) emitValueChange?.(emitted);
    else emitValueChange?.(emitted, details);
  };
  // Highlight changes move the virtual window, but do not change selection or loaded records.
  // Keep their data-sized work out of that path; real selection/page changes invalidate it.
  const { isSelected, allSelected, someSelected } = React.useMemo(() => {
    const isSelected = createSelectionMatcher(selectedValues);
    const allSelected = offeredValues.length > 0 && offeredValues.every(isSelected);
    return {
      isSelected,
      allSelected,
      someSelected: !allSelected && offeredValues.some(isSelected),
    };
  }, [selectedValues, offeredValues]);
  const visibleCount = Math.min(selectedValues.length, multiple ? Math.max(0, maxVisible) : 1);
  const hiddenCount = selectedValues.length - visibleCount;
  const overflow = hiddenCount > 0 ? overflowLabel(hiddenCount, { visibleCount }) : undefined;
  // Resolve only the bounded preview, not every selected record. No retained item cache or
  // duplicate collection index: supplied result records take precedence over known records.
  const preview = React.useMemo(
    () =>
      selectedValues
        .slice(0, visibleCount)
        .map((id) => {
          if (!getItemValue && !getItemLabel) return display(id);
          const item =
            filteredItems?.find((item) => Object.is(valueOf(item), id)) ??
            items.find((item) => Object.is(valueOf(item), id));
          return item === undefined ? display(id) : labelOf(item);
        })
        .join(", "),
    [
      selectedValues,
      visibleCount,
      getItemValue,
      getItemLabel,
      filteredItems,
      items,
      valueOf,
      labelOf,
      display,
    ],
  );
  const selection = multiple ? "checkbox" : "check";
  const renderItem = (item: Item) => (
    <ComboboxItem
      key={itemKey(valueOf(item))}
      title={labelOf(item)}
      {...getItemProps?.(item)}
      value={valueOf(item)}
      label={labelOf(item)}
      selection={selection}
    />
  );
  const triggerValue =
    selectedValues.length === 0
      ? (placeholder ?? null)
      : visibleCount === 0
        ? (overflow ?? null)
        : preview;

  return (
    <Field name={name} size={fieldSize} disabled={disabled} invalid={error != null || undefined}>
      <Combobox
        {...comboboxProps}
        virtualized={virtualized}
        onItemHighlighted={
          virtualized
            ? (item, details) => {
                setHighlight({ index: details.index, scroll: details.reason !== "pointer" });
                onItemHighlighted?.(item, details);
              }
            : onItemHighlighted
        }
        onInputValueChange={(next, details) => {
          onInputValueChange?.(next, details);
          if (virtualized && details.reason === "input-change" && !details.isCanceled) {
            bumpQueryEpoch();
          }
        }}
        multiple={multiple}
        disabled={disabled}
        items={collection}
        filteredItems={filteredItems}
        required={required}
        value={multiple ? selectedValues : (selectedValues[0] ?? null)}
        onValueChange={(next: Value[] | Value | null, details) => {
          selectValues(toSelection(next), details);
        }}
      >
        {label != null || description != null ? (
          <FieldLabelGroup orientation="vertical">
            {label != null ? (
              <FieldLabel id={labelId} size={fieldSize} inset={false} htmlFor={triggerId}>
                {label}
                {required ? <FieldLabelRequiredMarker>*</FieldLabelRequiredMarker> : null}
              </FieldLabel>
            ) : null}
            {description != null ? (
              <FieldDescription size={fieldSize}>{description}</FieldDescription>
            ) : null}
          </FieldLabelGroup>
        ) : null}
        <FieldControlContent orientation="vertical" size={fieldSize}>
          {variant === "pill" ? (
            <ComboboxTrigger
              id={triggerId}
              size={size}
              variant="pill"
              icon={icon}
              trailing={trailing}
              overflow={visibleCount > 0 ? overflow : undefined}
              aria-label={ariaLabel}
            >
              {triggerValue}
            </ComboboxTrigger>
          ) : (
            <ComboboxTrigger
              id={triggerId}
              size={size}
              variant={variant}
              width={width}
              icon={icon}
              trailing={trailing}
              overflow={visibleCount > 0 ? overflow : undefined}
              aria-label={ariaLabel}
            >
              {triggerValue}
            </ComboboxTrigger>
          )}
          <FieldHelperText size={fieldSize} hint={hint} error={error} />
        </FieldControlContent>
        <ComboboxContent
          aria-labelledby={label != null ? labelId : undefined}
          aria-label={label == null ? ariaLabel : undefined}
          sizing={
            sizing ??
            // A pill or fit-width field trigger is too narrow to set the popup's width, so it
            // takes the content's width; a windowed list keeps the 288px height cap either way.
            (hasCompactTrigger
              ? virtualized
                ? "auto-fixed"
                : "auto"
              : virtualized
                ? "anchor-fixed"
                : "anchor")
          }
          footer={footer}
          viewportRef={virtualized ? setViewport : undefined}
          search={
            <>
              <ComboboxSearch aria-label={searchLabel} placeholder={searchLabel} />
              {/* Select all and the divider under it exist only with `multiple`; alone, the
                  divider would be an orphan line under the search. */}
              {multiple ? (
                <ComboboxStickyList>
                  <ComboboxSelectAll
                    label={selectAllLabel}
                    checked={allSelected}
                    indeterminate={someSelected}
                    disabled={disabled || comboboxProps.readOnly || offeredValues.length === 0}
                    onClick={() => {
                      const isLoaded = createSelectionMatcher(offeredValues);
                      selectValues(
                        allSelected
                          ? selectedValues.filter((id) => !isLoaded(id))
                          : // A Set, because accumulated server pages can repeat an ID.
                            [...new Set([...selectedValues, ...offeredValues])],
                      );
                    }}
                  />
                  <ComboboxSeparator />
                </ComboboxStickyList>
              ) : null}
            </>
          }
        >
          <ComboboxEmpty>{empty}</ComboboxEmpty>
          {virtualized ? (
            <ComboboxFieldVirtualList
              viewport={viewport}
              highlight={highlight}
              queryEpoch={queryEpoch}
              display={labelOf}
              getItemValue={valueOf}
              getItemKey={keyOf}
              getItemProps={getItemProps}
              selection={selection}
            />
          ) : (
            <ComboboxList>{renderItem}</ComboboxList>
          )}
        </ComboboxContent>
      </Combobox>
    </Field>
  );
}

type ComboboxValueChangeDetails<Value> = Parameters<
  NonNullable<ComboboxProps<Value, true>["onValueChange"]>
>[1];

/** One value, several, or none, as the selection array the field keeps internally. */
function toSelection<V extends string | number>(value: readonly V[] | V | null | undefined): V[] {
  if (value == null) return [];
  return Array.isArray(value) ? [...value] : [value as V];
}

// React coerces keys to strings; retain the distinctions used by Object.is selection.
function itemKey(item: string | number): string {
  return `${typeof item}:${Object.is(item, -0) ? "-0" : item}`;
}

/** Narrow unknown items to the field's primitive Value without a type assertion. */
function isOptionValue<V extends string | number>(item: unknown): item is V {
  return typeof item === "string" || typeof item === "number";
}

/** Memoized row so highlight/scroll updates only re-render rows whose props change. */
const VirtualRow = React.memo(ComboboxItem);

type ComboboxFieldVirtualListProps<Value, Item> = {
  viewport: HTMLDivElement | null;
  highlight: { index: number; scroll: boolean };
  queryEpoch: number;
  display: (item: Item) => string;
  getItemValue: (item: Item) => Value;
  getItemKey: (item: Item) => React.Key;
  getItemProps: ((item: Item) => ComboboxFieldItemProps) | undefined;
  selection: ComboboxItemProps["selection"];
};

/**
 * Windowed option list. Must render under `Combobox` so `useFilteredItems` reads the active
 * collection. Not exported — one consumer today.
 */
function ComboboxFieldVirtualList<Value, Item>({
  viewport,
  highlight,
  queryEpoch,
  display,
  getItemValue,
  getItemKey,
  getItemProps,
  selection,
}: ComboboxFieldVirtualListProps<Value, Item>) {
  const items = BaseCombobox.useFilteredItems<Item>();
  const highlightedIndex = highlight.index;
  const keyAtIndex = React.useCallback(
    (index: number) => getItemKey(items[index]),
    [items, getItemKey],
  );
  // aria-activedescendant and immediate Enter must work before a scroll event updates the window.
  const rangeExtractor = React.useCallback(
    (range: Range) => {
      const indices = defaultRangeExtractor(range);
      if (
        highlightedIndex >= 0 &&
        highlightedIndex < range.count &&
        !indices.includes(highlightedIndex)
      ) {
        return [...indices, highlightedIndex].sort((a, b) => a - b);
      }
      return indices;
    },
    [highlightedIndex],
  );
  const virtualizer = useVirtualizer<HTMLDivElement, HTMLDivElement>({
    count: items.length,
    getScrollElement: () => viewport,
    estimateSize: () => MENU_ROW_SINGLE_HEIGHT_PX,
    overscan: 8,
    getItemKey: keyAtIndex,
    rangeExtractor,
    // Defer measure/scroll RO callbacks to the next frame so a mid-open popup height change
    // cannot re-enter the virtualizer from inside the same ResizeObserver delivery.
    useAnimationFrameWithResizeObserver: true,
    // The popup owns the existing inset; it is not additional list padding.
    scrollMargin: COMBOBOX_LIST_INSET_PX,
    scrollPaddingStart: COMBOBOX_LIST_INSET_PX,
    scrollPaddingEnd: COMBOBOX_LIST_INSET_PX,
  });
  React.useLayoutEffect(() => {
    if (viewport && highlight.scroll && highlight.index >= 0) {
      virtualizer.scrollToIndex(highlight.index, { align: "auto" });
    }
  }, [viewport, virtualizer, highlight]);
  React.useLayoutEffect(() => {
    if (viewport && queryEpoch > 0) virtualizer.scrollToOffset(0);
  }, [queryEpoch, viewport, virtualizer]);

  return (
    <ComboboxList>
      <ComboboxListSpacer extent={virtualizer.getTotalSize()}>
        {virtualizer.getVirtualItems().map((row) => {
          const label = display(items[row.index]);
          return (
            <ComboboxItemPositioner
              key={row.key}
              offset={row.start - COMBOBOX_LIST_INSET_PX}
              data-index={row.index}
              render={<div ref={virtualizer.measureElement} />}
            >
              <VirtualRow
                title={label}
                {...getItemProps?.(items[row.index])}
                index={row.index}
                value={getItemValue(items[row.index])}
                label={label}
                selection={selection}
                aria-posinset={row.index + 1}
                aria-setsize={items.length}
              />
            </ComboboxItemPositioner>
          );
        })}
      </ComboboxListSpacer>
    </ComboboxList>
  );
}
