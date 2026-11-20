import { cva } from "class-variance-authority";
import type { DayPickerProps } from "react-day-picker";

// The two nav buttons are identical 28px transparent icon buttons that tint on hover (Figma "Icon
// buttons"). DayPicker's default Nav uses `aria-disabled`, while Calendar's custom Nav uses native
// `disabled`; both receive the system-wide disabled dim.
const navButton =
  "inline-flex size-7 cursor-pointer items-center justify-center rounded-md text-icon-tertiary hover:bg-layer-transparent-hover aria-disabled:cursor-not-allowed aria-disabled:opacity-60 disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:bg-transparent";

// Propel-token class map for react-day-picker's UI parts. We never import its
// default stylesheet — every visual decision below comes from a propel utility
// (Figma node 1272-11630): 40px round day cells, accent endpoints, soft in-range
// fill. Keys mirror react-day-picker's `UI`/`DayFlag`/`SelectionState` enums.
//
// The grid draws no surface of its own. Figma's bordered, elevated calendar frame is the date
// picker's *popup*, and in code that popup is the host — a `rich` `PopoverContent`, a dialog, a
// card — which already paints the border, shadow, fill, radius and gutters. When the root carried
// that chrome too, every real placement showed a card inside a card: two borders, two shadows,
// 32px of padding, and on the dark theme an inner fill darker than the popup around it. The
// calendars in shadcn/ui, MUI, Mantine and React Aria are bare for the same reason.
export const calendarClassNames: Partial<NonNullable<DayPickerProps["classNames"]>> = {
  // Bare, shrink-wrapped root: `relative` anchors the absolutely positioned `nav`; `w-fit` keeps
  // it the 280px grid's width — also as a flex item in a popover's column, which would otherwise
  // stretch it — so the nav's inline-end lines up with the last column.
  root: "relative w-fit",
  months: "flex flex-col gap-3",
  month: "flex flex-col gap-3",
  // Caption + nav share one row; the label leads, buttons sit at the end.
  month_caption: "flex items-center h-7",
  caption_label: "text-h5-semibold text-secondary",
  // Pinned to the root's own top/inline-end corner when a caller uses DayPicker's Nav part.
  nav: "absolute inset-e-0 top-0 flex items-center gap-1",
  button_previous: navButton,
  button_next: navButton,
  // The nav chevron: 16px, mirrored in RTL. react-day-picker passes this class to its `Chevron`
  // component (default or a custom one), so the icon needs no className of its own.
  chevron: "size-4 rtl:-scale-x-100",
  month_grid: "border-collapse",
  weekdays: "flex",
  // Weekday column headers: body-sm-regular tertiary text on a 40px cell. The
  // composite `text-body-sm-regular` utility carries the 14px size plus the
  // propel regular weight/line-height (Figma "font/body-sm/regular").
  weekday: "flex size-10 items-center justify-center text-body-sm-regular text-tertiary",
  week: "flex w-full",
  // react-day-picker v10 applies the modifier classNames (`selected`, `today`,
  // `range_*`) and `aria-selected` to the gridcell (this `td`) itself — NOT to a
  // descendant — so we target the cell directly with `[&.foo]`/`[&[aria-selected]]`
  // and reach the inner button with `[&>button]`.
  //
  // The cell is the range backdrop: range cells (start/middle/end) get the soft
  // in-range fill, and only the outer corners of an endpoint round off so a
  // continuous range reads as one pill. A plain single-selected cell stays
  // transparent (its solid pill comes from the button below).
  day: "relative size-10 p-0 text-center [&.range-start]:bg-accent-subtle-hover [&.range-middle]:bg-accent-subtle-hover [&.range-end]:bg-accent-subtle-hover [&.range-start]:rounded-s-full [&.range-end]:rounded-e-full",
  // The actual button: 40px round, body-sm text, primary color.
  day_button:
    "relative inline-flex size-10 cursor-pointer items-center justify-center rounded-full text-body-sm-regular text-primary hover:bg-layer-transparent-hover",
  // Selected single day / range endpoints: solid accent button, inverse text.
  // (`selected` is set on the cell for every day in a range; `range_middle`
  // below resets the button back to transparent for the in-between days.)
  // `text-inverse` keeps AA contrast on the brand-blue surface in every theme.
  selected:
    "[&>button]:bg-accent-primary [&>button]:text-inverse [&>button:hover]:bg-accent-primary",
  // Endpoints are tagged so the cell can round the outer edge of the range.
  range_start: "range-start",
  range_end: "range-end",
  // Middle of a range: keep the button transparent so only the cell's soft fill
  // shows, and square the cell (the marker class also drives the fill above).
  range_middle:
    "range-middle [&>button]:bg-transparent [&>button]:text-primary [&>button:hover]:bg-transparent",
  // A 6px accent dot sits centered 4px above the cell's bottom edge in every
  // state. The date text keeps its normal color and weight, as in Figma's Dates
  // states; a selected day still gets the solid accent button above.
  today:
    "after:absolute after:bottom-1 after:left-1/2 after:-translate-x-1/2 after:size-1.5 after:rounded-full after:bg-(--txt-icon-accent-subtle)",
  // Disabled days read as muted, non-interactive text via the disabled variant alone (matching every
  // other disabled control — no extra opacity), so they recede without going lighter than Figma.
  // `cursor-not-allowed` sits on the cell, not `[&>button]`: the button's own
  // `pointer-events-none` skips its hit-testing, so a cursor set on the button itself
  // never renders — the cell (still `auto`) is what the pointer resolves to instead.
  disabled: "cursor-not-allowed [&>button]:text-disabled [&>button]:pointer-events-none",
  // Days from the adjacent month: dimmed.
  outside: "[&>button]:text-tertiary",
  hidden: "invisible",
};

// Month and year views share Figma's 280px content area inside the host's 16px gutters. The
// DayPicker grid above stays bare; these parts likewise leave the card surface to the host.
export const calendarViewVariants = cva("relative flex w-70 flex-col gap-3");

export const calendarViewHeaderVariants = cva("flex h-7 w-full items-center justify-between");

export const calendarViewHeadingVariants = cva("flex items-center");

export const calendarViewTitleVariants = cva("px-1.5 text-h5-semibold text-secondary");

// The caption's glyph is supplied by components, keeping the styled element icon-agnostic.
export const calendarViewSwitchVariants = cva(
  "inline-flex h-7 min-w-12 cursor-pointer items-center justify-center gap-1 rounded-md px-1.5 text-h5-semibold text-secondary [--node-size:var(--control-glyph-sm)] hover:bg-layer-transparent-hover focus-visible:ring-2 focus-visible:ring-accent-strong",
);

export const calendarViewNavVariants = cva("absolute inset-e-0 top-0 flex items-center gap-1");

// Four 40px rows are distributed across the 240px body, matching the month/year design.
export const calendarViewGridVariants = cva(
  "grid h-60 w-full grid-cols-3 grid-rows-[repeat(4,40px)] content-between",
);

// `data-active` marks the option containing the currently displayed month/year.
export const calendarViewOptionVariants = cva(
  "inline-flex h-10 w-full min-w-13 cursor-pointer items-center justify-center rounded-md px-3 text-body-sm-medium text-secondary hover:bg-layer-transparent-hover focus-visible:ring-2 focus-visible:ring-accent-strong active:bg-layer-transparent-active disabled:cursor-not-allowed disabled:text-disabled disabled:hover:bg-transparent data-active:bg-layer-transparent-active data-active:hover:bg-layer-transparent-active",
);
