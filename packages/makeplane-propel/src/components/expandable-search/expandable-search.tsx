import * as React from "react";

import {
  ExpandableSearchRow,
  ExpandableSearchTrack,
  ExpandableSearchTrigger,
} from "../../elements/expandable-search";
import { useControllableState } from "../../hooks/use-controllable-state";
import { SearchOutline, CloseOutline } from "../../icons";
import {
  Autocomplete,
  AutocompleteInputGroup,
  type AutocompleteProps,
  type AutocompleteSize,
} from "../autocomplete";
import { Icon } from "../icon";
import { IconButton, type IconButtonSize } from "../icon-button";

// The icon button rung inside each row rung: one ladder rung down, matching the clear/trigger
// buttons in `Autocomplete`'s own stories — a 28/32/36/40px row seats a 24/28/32/32px icon
// button. The compact scale tops out at `lg` (32px), so `xl` and `2xl` rows both clamp there.
const ICON_BUTTON_SIZE: Record<AutocompleteSize, IconButtonSize> = {
  md: "sm",
  lg: "md",
  xl: "lg",
  "2xl": "lg",
};

export type ExpandableSearchProps<Value = string> = Omit<AutocompleteProps<Value>, "children"> & {
  /** Accessible name applied to both the collapsed trigger and the expanded input. */
  "aria-label": string;
  /** Accessible name for the clear button shown once the input has a value. Localizable. */
  clearLabel: string;
  /**
   * Size, shared by the collapsed trigger and the expanded input row (same scale as
   * `Autocomplete`). The trigger/clear `IconButton`s step one ladder rung below it (see
   * `ICON_BUTTON_SIZE`), so the collapsed icon reads as a smaller control inside the expanded row's
   * own box — `ExpandableSearchTrigger` pads that box up to the row's height at the same step, so
   * toggling between them never shifts height.
   */
  size: AutocompleteSize;
  /**
   * Input placeholder shown once expanded.
   *
   * @default "Search…"
   */
  placeholder?: string;
  /**
   * Controlled expand state. When set, the trigger/row visibility is driven by the consumer (e.g. a
   * `/` shortcut). Pair with `onExpandedChange`. Distinct from Autocomplete's `open` (popup).
   */
  expanded?: boolean;
  /**
   * Uncontrolled initial expand state. Defaults to expanded when `value`/`defaultValue` is
   * non-empty so a pre-filled search is not trapped under an inert trigger.
   */
  defaultExpanded?: boolean;
  /** Called when expand state changes, in both controlled and uncontrolled mode. */
  onExpandedChange?: (expanded: boolean) => void;
  /** Popup content (e.g. `AutocompleteContent`) shown once expanded, when `items` are provided. */
  children?: React.ReactNode;
};

function isFilledValue(value: unknown): boolean {
  if (value == null) return false;
  if (typeof value === "string") return value.length > 0;
  if (Array.isArray(value)) return value.length > 0;
  return true;
}

/**
 * A collapsed icon trigger that expands into a search input on click, collapsing again on blur or
 * Escape while empty — unless it's `required` and still invalid, in which case it stays expanded so
 * the field remains focusable instead of collapsing back into an inert trigger. Escape restores
 * focus to the trigger. Expand is controllable via `expanded`/`defaultExpanded`/`onExpandedChange`
 * (separate from Autocomplete's popup `open`). Built on `Autocomplete` — pass `items` and
 * `children` (e.g. `AutocompleteContent`) for suggestions, or omit both for a plain search box.
 * Without `children` the popup is forced closed (no listbox ever mounts), so a plain search box
 * never claims `aria-expanded`. Non-empty `value`/`defaultValue` starts expanded (and controlled
 * non-empty `value` keeps it expanded); a controlled `open` is forced closed while collapsed so a
 * popup never mounts over an inert input. The `Autocomplete` root and its input stay mounted at
 * every state — the trigger/row swap width via an animated CSS grid track and `inert` instead of
 * unmounting or `hidden` — so a `required`/`defaultValue` input keeps working under native form
 * validation and keeps its own state across collapse/expand instead of resetting.
 */
export function ExpandableSearch<Value = string>({
  "aria-label": ariaLabel,
  clearLabel,
  size,
  placeholder = "Search…",
  children,
  open,
  disabled,
  value,
  defaultValue,
  expanded: expandedProp,
  defaultExpanded,
  onExpandedChange,
  ...rootProps
}: ExpandableSearchProps<Value>) {
  const [expanded, setExpanded] = useControllableState({
    value: expandedProp,
    defaultValue: defaultExpanded ?? isFilledValue(value ?? defaultValue),
    onValueChange: onExpandedChange,
  });
  const inputRef = React.useRef<HTMLInputElement>(null);
  const triggerRef = React.useRef<HTMLButtonElement>(null);
  // Escape collapse must restore focus to the trigger *after* inert clears (focusing while the
  // trigger is still inert is a no-op). Blur collapse leaves focus where the user went — skip it.
  const restoreTriggerFocusRef = React.useRef(false);

  // Controlled non-empty value → expand (e.g. parent fills the field while still collapsed).
  // Empty → leave collapse to blur; auto-collapsing mid-edit would yank focus into the trigger.
  // When `expanded` is also controlled this only notifies via `onExpandedChange`.
  React.useEffect(() => {
    if (value !== undefined && isFilledValue(value)) setExpanded(true);
  }, [value, setExpanded]);

  // The input stays mounted across collapse/expand, so browser `autoFocus` only helps on first
  // paint. Re-focus the input when we *transition* into expanded (click, controlled expand,
  // `onInvalid`) — but skip the initial mount so a prefilled `defaultValue`/`value` (or
  // `defaultExpanded`) does not steal document focus. Escape collapse flips the other way:
  // restore focus to the trigger once it is no longer inert.
  const wasExpandedRef = React.useRef(expanded);
  React.useEffect(() => {
    const becameExpanded = expanded && !wasExpandedRef.current;
    const becameCollapsed = !expanded && wasExpandedRef.current;
    wasExpandedRef.current = expanded;

    if (becameExpanded) {
      inputRef.current?.focus();
      return;
    }
    if (becameCollapsed && restoreTriggerFocusRef.current) {
      restoreTriggerFocusRef.current = false;
      triggerRef.current?.focus();
    }
  }, [expanded]);

  // Popup stays closed while the row is collapsed when the consumer controls `open`. Uncontrolled
  // suggestions keep `undefined` so Base UI owns open for the whole lifetime (no controlled flip).
  const resolvedOpen =
    open !== undefined ? (expanded ? open : false) : children != null ? undefined : false;

  return (
    <Autocomplete
      open={resolvedOpen}
      disabled={disabled}
      value={value}
      defaultValue={defaultValue}
      {...rootProps}
    >
      {/* Stacks the trigger and the row on top of each other (same grid cell) so one grows in place
          as the other shrinks, rather than rendering as two sequential boxes. Width/opacity animate
          via each one's own CSS grid track (`data-expanded`); `inert` (not `hidden`, which can't
          transition) removes the collapsed one from focus/AT. */}
      <ExpandableSearchTrack>
        {/* Padded to the expanded row's own height (rather than the smaller `IconButton` box it
            holds) so collapsing/expanding never shifts height. */}
        <ExpandableSearchTrigger
          size={size}
          data-expanded={expanded ? "" : undefined}
          inert={expanded}
        >
          <IconButton
            ref={triggerRef}
            variant="ghost"
            size={ICON_BUTTON_SIZE[size]}
            aria-label={ariaLabel}
            aria-expanded={expanded}
            icon={<Icon icon={SearchOutline} />}
            disabled={disabled}
            onClick={() => setExpanded(true)}
          />
        </ExpandableSearchTrigger>
        <ExpandableSearchRow data-expanded={expanded ? "" : undefined} inert={!expanded}>
          <AutocompleteInputGroup
            ref={inputRef}
            size={size}
            placeholder={placeholder}
            aria-label={ariaLabel}
            icon={<Icon icon={SearchOutline} tint="placeholder" />}
            // A collapsed `required` input is inert, so the browser's own attempt to focus it
            // during native validation silently fails — expand first; the `expanded` effect above
            // then focuses it once the row is no longer inert.
            onInvalid={() => setExpanded(true)}
            // Without `children` there is no popup, ever — override Base UI's combobox ARIA
            // (baked in regardless of `open`) so the input announces as a plain `searchbox`.
            {...(children == null && {
              role: "searchbox",
              "aria-haspopup": undefined,
              "aria-expanded": undefined,
              "aria-autocomplete": undefined,
            })}
            clear={
              <IconButton
                variant="ghost"
                size={ICON_BUTTON_SIZE[size]}
                aria-label={clearLabel}
                icon={<Icon icon={CloseOutline} />}
              />
            }
            // Escape is the keyboard exit that Tab is not: collapse while empty (and valid) and
            // put focus back on the trigger instead of dumping it onto the next tab stop.
            onKeyDown={(event) => {
              if (event.key !== "Escape") return;
              if (event.currentTarget.value !== "" || !event.currentTarget.validity.valid) return;
              event.preventDefault();
              restoreTriggerFocusRef.current = true;
              setExpanded(false);
            }}
            // Skip collapsing while still invalid (e.g. empty + required) — otherwise blurring
            // away from the input `onInvalid` just expanded would re-`inert` it right back.
            onBlur={(event) => {
              if (event.target.value === "" && event.target.validity.valid) setExpanded(false);
            }}
          />
        </ExpandableSearchRow>
      </ExpandableSearchTrack>
      {children}
    </Autocomplete>
  );
}
