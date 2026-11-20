import { Autocomplete as BaseAutocomplete } from "@base-ui/react/autocomplete";
import * as React from "react";

import {
  AutocompleteEmpty,
  AutocompleteInput,
  AutocompleteInputGroup,
  AutocompleteInputGroupClear,
} from "../../elements/autocomplete/index";
import type { FieldSize } from "../../elements/field/variants";
import { DROPDOWN_EDGE_GAP_PX } from "../../internal/dropdown-edge-gap";
import { ListboxItem } from "../../internal/listbox-item";
import { ListboxPopup } from "../../internal/listbox-popup";
import { Positioner } from "../../internal/positioner";
import {
  Autocomplete,
  type AutocompleteProps,
  AutocompleteStatus,
  useFilteredItems,
} from "../autocomplete";
import { Field, FieldDescription, FieldLabel } from "../field";
import { FieldHelperText } from "../field/field-helper-text";

export type { FieldSize };

type AutocompleteFieldSharedProps<Value> = Omit<
  AutocompleteProps<Value>,
  "children" | "items" | "filteredItems"
> & {
  /** Supporting text shown below the input. Replaced by `error` when an error is set. */
  description?: React.ReactNode;
  /**
   * The clear control (e.g. an `IconButton`) carrying its own localizable `aria-label`. Required
   * here (unlike the bare `AutocompleteInputGroup`) — a labeled field is always presented as a
   * complete picker, not a plain search box.
   */
  clear: React.ReactElement;
  /**
   * The popup-trigger control (e.g. an `IconButton`) carrying its own localizable `aria-label`.
   * Required here for the same reason as `clear`.
   */
  trigger: React.ReactElement;
  /** Message rendered when no item matches. */
  empty: React.ReactNode;
  /** Error text shown below the control. */
  error?: React.ReactNode;
  /** Helper text shown below the control. Replaced by `error` when an error is set. */
  hint?: React.ReactNode;
  /**
   * Searchable catalog in local mode, or loaded results with `filteredItems` in external mode. Only
   * the first `limit` matches render. The limit bounds rendering, not full-catalog filtering; use
   * external search for huge catalogs. Use ComboboxField to scroll accumulated results.
   */
  items: readonly Value[];
  /** Externally filtered or server-ranked matches. The same result limit applies to this list. */
  filteredItems?: readonly Value[];
  /**
   * Maximum displayed matches for local and external filtering. Use `-1` only for a bounded list
   * that must display every match. `0` renders no rows, but the popup still opens and shows `empty`
   * even when matches exist — it is not a “hold suggestions back” mode. This never truncates the
   * source catalog.
   *
   * @default 50
   */
  limit?: number;
  /**
   * Announced in the popup when the result cap may be hiding matches (shown count equals `limit`
   * and the source list is longer). Override to localize; pass `null` to suppress the hint.
   *
   * @default "Showing the first {limit} matches. Keep typing to narrow results."
   */
  truncatedMessage?: React.ReactNode | null;
  /** Visible field label. */
  label: string;
  /** Label and helper text size. */
  size: FieldSize;
  /** Input placeholder. */
  placeholder?: string;
};

/** Primitive string/number options. `getItemKey` is optional — each unique primitive keys as itself. */
export type AutocompleteFieldProps<Value extends React.Key = string> =
  AutocompleteFieldSharedProps<Value> & {
    /**
     * Stable unique identity for each result. Defaults to the item itself for unique primitives.
     * Preserve keys across server response replacements and reordering; labels may repeat.
     */
    getItemKey?: (item: Value) => React.Key;
  };

/**
 * Record options. `getItemKey` is required so equal labels stay distinct — pass `(item) => item.id`
 * (or another stable unique identity). Preserve keys across server response replacements and
 * reordering.
 */
export type AutocompleteFieldRecordProps<Value extends object> =
  AutocompleteFieldSharedProps<Value> & {
    /**
     * Stable, unique identity for each result, independent of its display label or current index.
     * Required for record options: labels may repeat, and object identity is not enough when a
     * server replaces or reorders results. Primitive string/number options key as themselves.
     */
    getItemKey: (item: Value) => React.Key;
  };

type AutocompleteFieldImplProps<Value> = AutocompleteFieldSharedProps<Value> & {
  getItemKey?: (item: Value) => React.Key;
};

let warnedMissingItemKey = false;
function warnMissingItemKey() {
  if (warnedMissingItemKey) return;
  warnedMissingItemKey = true;
  console.error(
    "AutocompleteField: record options need `getItemKey`. Rows are keyed by position until it's passed.",
  );
}

/** Accurate even when the matches land exactly on the cap. */
function defaultTruncatedMessage(limit: number) {
  return `Showing the first ${limit} matches. Keep typing to narrow results.`;
}

/**
 * Live region that announces when the result cap may have hidden matches. Must render under the
 * Autocomplete root so `useFilteredItems` reads the active (already limited) collection — no second
 * full-catalog filter pass.
 *
 * Local mode cannot know an exact remainder without re-running the caller's filter, so the hint is
 * possibly-truncated: shown count hit `limit` and the source list is longer. External mode uses the
 * pre-cap `filteredItems` length the same way.
 */
function TruncatedStatus({
  limit,
  sourceCount,
  message,
}: {
  limit: number;
  sourceCount: number;
  message: React.ReactNode;
}) {
  const shown = useFilteredItems().length;
  const mayTruncate = limit > 0 && shown === limit && sourceCount > limit;
  return <AutocompleteStatus>{mayTruncate ? message : null}</AutocompleteStatus>;
}

/**
 * Ready-to-use autocomplete field with label, input, popup items, and helper/error text.
 *
 * Record options require `getItemKey`. Primitive string/number options key as themselves when it is
 * omitted.
 */
export function AutocompleteField<Value extends object>(
  props: AutocompleteFieldRecordProps<Value>,
): React.JSX.Element;
export function AutocompleteField<Value extends React.Key = string>(
  props: AutocompleteFieldProps<Value>,
): React.JSX.Element;
export function AutocompleteField<Value = string>({
  description,
  clear,
  trigger,
  disabled,
  empty,
  error,
  hint,
  items,
  getItemKey,
  filteredItems,
  limit = 50,
  truncatedMessage,
  label,
  size,
  name,
  placeholder,
  ...autocompleteProps
}: AutocompleteFieldImplProps<Value>) {
  // Base UI's itemToStringValue turns an object item into the input's string; the suggestion rows
  // display the same string.
  const display = (item: Value) =>
    autocompleteProps.itemToStringValue ? autocompleteProps.itemToStringValue(item) : String(item);
  const itemKey = (item: Value, index: number): React.Key => {
    if (getItemKey) return getItemKey(item);
    // React.Key is string | number | bigint; primitives key as themselves without getItemKey.
    if (typeof item === "string" || typeof item === "number" || typeof item === "bigint") {
      return item;
    }
    // A record without `getItemKey` has no identity we can know (types require it; this covers
    // untyped callers). Key by position, as React does without a key: option rows hold no state.
    if (process.env.NODE_ENV !== "production") warnMissingItemKey();
    return index;
  };

  // Cap external lists before Base UI; local mode still relies on root `limit`. Source length is the
  // pre-cap external list or the full local catalog — enough for a possibly-truncated hint without a
  // second filter pass.
  const cappedFilteredItems = React.useMemo(
    () => (filteredItems && limit >= 0 ? filteredItems.slice(0, limit) : filteredItems),
    [filteredItems, limit],
  );
  const sourceCount = filteredItems != null ? filteredItems.length : items.length;

  return (
    <Field name={name} disabled={disabled} invalid={error != null || undefined}>
      <Autocomplete
        {...autocompleteProps}
        disabled={disabled}
        items={items}
        limit={limit}
        filteredItems={cappedFilteredItems}
      >
        <FieldLabel size={size} inset={false}>
          {label}
        </FieldLabel>
        <BaseAutocomplete.InputGroup render={<AutocompleteInputGroup size={size} />}>
          <BaseAutocomplete.Input render={<AutocompleteInput />} placeholder={placeholder} />
          <AutocompleteInputGroupClear>
            <BaseAutocomplete.Clear render={clear} keepMounted />
          </AutocompleteInputGroupClear>
          <BaseAutocomplete.Trigger render={trigger} />
        </BaseAutocomplete.InputGroup>
        {error == null && description != null ? (
          <FieldDescription size={size}>{description}</FieldDescription>
        ) : null}
        <BaseAutocomplete.Portal>
          <BaseAutocomplete.Positioner
            collisionPadding={DROPDOWN_EDGE_GAP_PX}
            render={<Positioner />}
          >
            <BaseAutocomplete.Popup render={<ListboxPopup />}>
              <BaseAutocomplete.Empty render={<AutocompleteEmpty />}>
                {empty}
              </BaseAutocomplete.Empty>
              <BaseAutocomplete.List>
                {(item: Value, index: number) => (
                  <BaseAutocomplete.Item
                    key={itemKey(item, index)}
                    value={item}
                    render={<ListboxItem size={size} />}
                  >
                    {display(item)}
                  </BaseAutocomplete.Item>
                )}
              </BaseAutocomplete.List>
              {truncatedMessage !== null ? (
                <TruncatedStatus
                  limit={limit}
                  sourceCount={sourceCount}
                  message={truncatedMessage ?? defaultTruncatedMessage(limit)}
                />
              ) : null}
            </BaseAutocomplete.Popup>
          </BaseAutocomplete.Positioner>
        </BaseAutocomplete.Portal>
        <FieldHelperText size={size} hint={hint} error={error} />
      </Autocomplete>
    </Field>
  );
}
