import { cva, cx, type VariantProps } from "class-variance-authority";

import { nodeSlotClass } from "../../internal/node-slot";
import { type StrictVariantProps } from "../../internal/variant-props";

// Table is a structural data primitive. The designer locked two layout looks (Figma
// "Table" vs "Spreadsheet") as the only `variant` axis, and baked everything else
// (header chrome, cell padding, row hover, sort-indicator position, focus ring) into
// the component so every table stays consistent. `plain` is a third look on the same axis: the
// `table` metrics with the frame and the fills removed, for a table that sits directly on the
// page. Every part's className lives here as
// a cva pairing, so no part takes a `className` at its boundary.

// The two framed looks share one frame and one set of fills; only their cell borders differ. Both
// are named once here so a change to the frame cannot reach one look and miss the other.
const framedVariants: ["table", "spreadsheet"] = ["table", "spreadsheet"];
const tableFrameClass = "rounded-lg border border-subtle bg-surface-1";

// The opaque fill a `plain` table's sticky parts paint: its header, and any pinned cell. They
// cannot be transparent — the body would read through them while scrolling — so they paint the
// surface the table sits on. That is `surface-1` unless the host says otherwise by setting
// `--table-surface` on any ancestor of the table, e.g. `[--table-surface:var(--bg-layer-2)]` on a
// `layer-2` panel. Parts take no `className`, so this property is the one lever a host has.
const plainSurfaceClass = "bg-[color:var(--table-surface,var(--bg-surface-1))]";

const tableScrollAreaDefaultVariants = {
  variant: "table",
} as const;

// The scroll frame around the `<table>`: rounded and hairline-bordered for the two framed looks,
// bare for `plain`. The ready-made grafts the Base UI ScrollArea.Root onto this styled frame via
// `render`.
export const tableScrollAreaVariants = cva(
  "relative flex max-h-full w-full flex-col overflow-hidden",
  {
    variants: {
      /** The surrounding table look. `plain` draws no frame, so the table sits on the page. */
      variant: {
        table: tableFrameClass,
        spreadsheet: tableFrameClass,
        plain: "",
      },
    },
    defaultVariants: tableScrollAreaDefaultVariants,
  },
);

export type TableScrollAreaVariantProps = StrictVariantProps<
  typeof tableScrollAreaVariants,
  keyof typeof tableScrollAreaDefaultVariants
>;

// The scroll viewport that the `<table>` lives in. The `group/table-viewport` marker lets pinned
// heads/cells read Base UI's `data-overflow-x-start`/`data-overflow-x-end` scroll state to cast
// their directional shadow only while content is scrolled behind them.
export const tableScrollAreaViewportVariants = cva(
  cx(
    "group/table-viewport min-h-0 flex-1 overscroll-x-contain rounded-[inherit] outline-none",
    "focus-visible:ring-2 focus-visible:ring-accent-strong focus-visible:ring-inset",
  ),
);

// The `<table>` element itself.
//
// It also owns the three lengths the expandable-row geometry is built from, as custom properties
// the parts below read: a cell's inline padding, the gap between the items in a cell, and the
// expand control's size. The header's `inset="expand"` is their sum, so the header label cannot
// drift from the row content it lines up with when one of them changes.
export const tableVariants = cva(
  cx(
    "w-full caption-bottom border-collapse text-body-xs-regular text-primary",
    "[--table-cell-gap:0.375rem] [--table-cell-padding-x:0.75rem] [--table-expand-size:1rem]",
  ),
);

// `<thead>` / `<tbody>` carry no chrome of their own; the cva keeps every part styled
// in one place even when the pairing is empty.
export const tableHeaderVariants = cva("");

export const tableBodyVariants = cva("");

// The `<tbody>` of a loading table. The pulse lives on the body — as it does on the Skeleton region
// — so every bone fades on one timeline instead of each starting its own.
//
// `pointer-events-none` is how a placeholder row opts out of the row hover tint: `tableRowVariants`
// welds `hover:bg-layer-transparent-hover` into its unselected branch, and propel forbids
// tailwind-merge, so a second background utility on the row could not override it deterministically.
// Removing the hit target removes the hover instead.
export const tableSkeletonBodyVariants = cva(
  "pointer-events-none animate-pulse motion-reduce:animate-none",
);

// A `<tr>` shared by thead + tbody. Header rows also use this part, but heads paint their own opaque
// fill (`bg-layer-1`, or the host surface in the `plain` look) so the body tints are masked. The `body-row` group name is kept so pinned cells can read
// `group-hover/body-row` / `group-data-selected/body-row` / `group-last/body-row`.
//
// Figma gives the Table cell three states, and the tints below are its bindings: default is the
// row's own `layer-2`, hover is `layer-transparent-hover` (4% black) and selected is
// `layer-transparent-selected` (8%) — design moved the selected state onto the selected token on
// 2026-09-11. Both tints are translucent so they compose over the frame. `layer-transparent-active`
// (6%) stays the open-menu tint on a cell trigger, so the three now read cleanly: hover, open,
// selected.
//
// The whole background lives inside the `selected` axis rather than the base, because propel forbids
// tailwind-merge: a `bg-layer-2` in the base plus a `bg-layer-transparent-selected` in a variant would
// resolve by CSS source order rather than deterministically.
const tableRowDefaultVariants = {
  variant: "table",
  selected: false,
  interactive: false,
  section: false,
} as const;

// Every background lives in `compoundVariants` so exactly ONE `bg-*` utility is ever emitted for a
// given combination. propel forbids tailwind-merge, so two background utilities on one row would
// resolve by CSS source order rather than deterministically — which is not hypothetical: a consumer
// reaching through `render` to paint a group header `bg-layer-1` had it silently overridden by the
// row's own `bg-layer-2`, and the row rendered identically to a data row.
//
// `plain` has no frame to sit on, so its resting row paints no fill at all and the page shows
// through; the hover, selected and section backgrounds are the same as the framed looks.
//
// A row is not focusable on its own, but `TableNestedRows` moves focus onto the first row it
// reveals, so the row carries a focus indicator for that case: an inset outline, because a ring is
// a `box-shadow` and table rows do not paint one under `border-collapse`. No `outline-none` reset
// beside it — that would suppress the outline it is paired with (see the toast viewport).
export const tableRowVariants = cva(
  cx(
    "group/body-row",
    "focus-visible:outline-md focus-visible:-outline-offset-2 focus-visible:outline-accent-strong",
  ),
  {
    variants: {
      /** The surrounding table look, which decides the resting row fill. */
      variant: { table: "", spreadsheet: "", plain: "" },
      /** Figma's `state=selected`. Also drives the pinned-cell overlay via `data-selected`. */
      selected: { true: "", false: "" },
      /**
       * Whether the row itself is a click target. Figma's hover state carries `cursor-pointer`, but
       * a read-only table should not advertise one, so the caller opts in.
       */
      interactive: { true: "cursor-pointer", false: "" },
      /**
       * A non-data row that labels the group of rows beneath it. It sits on `layer-1` — the
       * header's fill — and takes no hover tint, because there is nothing to act on.
       */
      section: { true: "", false: "" },
    },
    compoundVariants: [
      { selected: true, class: "bg-layer-transparent-selected" },
      {
        variant: framedVariants,
        selected: false,
        section: false,
        class: "bg-layer-2 hover:bg-layer-transparent-hover",
      },
      {
        variant: "plain",
        selected: false,
        section: false,
        class: "hover:bg-layer-transparent-hover",
      },
      { selected: false, section: true, class: "bg-layer-1" },
    ],
    defaultVariants: tableRowDefaultVariants,
  },
);

export type TableRowVariantProps = StrictVariantProps<
  typeof tableRowVariants,
  keyof typeof tableRowDefaultVariants
>;

// Directional pin shadows: cast from an `::after` box (Chrome skips `box-shadow` on cells under
// `border-collapse: collapse`). Shared by head + cell; only paints while the viewport reports
// overflow behind that edge (and flips with writing direction).
// Pinned cells stay opaque (`bg-layer-2`, or the host surface in the `plain` look) so
// content scrolling behind them does not read through, which rules out swapping in the translucent
// row tint. They paint the identical tints through a
// `::before` overlay instead, so a pinned column and the rest of its row match exactly in both
// states. Section rows use an opaque layer-1 base and no hover overlay. Selection still wins
// when both flags are set, matching the row compounds. `TableRow` exposes both data attributes.
const pinnedRowTint = cx(
  "before:pointer-events-none before:absolute before:inset-0",
  "group-[[data-section]:not([data-selected])]/body-row:bg-layer-1",
  "group-[:hover:not([data-section]):not([data-selected])]/body-row:before:bg-layer-transparent-hover",
  "group-data-selected/body-row:before:bg-layer-transparent-selected",
);

const pinnedOverflowShadowStart = cx(
  "after:pointer-events-none after:absolute after:inset-0 after:[clip-path:inset(0_-80px)]",
  "group-data-overflow-x-start/table-viewport:after:shadow-direction-right",
  "rtl:group-data-overflow-x-start/table-viewport:after:shadow-direction-left",
);
const pinnedOverflowShadowEnd = cx(
  "after:pointer-events-none after:absolute after:inset-0 after:[clip-path:inset(0_-80px)]",
  "group-data-overflow-x-end/table-viewport:after:shadow-direction-left",
  "rtl:group-data-overflow-x-end/table-viewport:after:shadow-direction-right",
);

// A header cell (`<th>`). `variant` is the table look; the row/edge borders come from
// the surrounding `Table`'s variant via `pinned`/`edge`. Sticky to the top so the
// header stays visible while the body scrolls (an "always").
const tableHeadDefaultVariants = {
  pinned: "none",
  align: "start",
  inset: "none",
} as const;

export const tableHeadVariants = cva(
  cx("sticky top-0 h-11 min-w-11 py-2 align-middle", "text-caption-md-semibold text-tertiary"),
  {
    variants: {
      // The surrounding table look, which decides this cell's borders. Both looks are 44px rows:
      // the component frames in Figma read 38px, but the composed examples are 44px in both
      // compositions and design confirmed 44px as the row height (2026-09-11).
      //
      // The header fill lives here rather than in the base so exactly one `bg-*` is emitted per
      // look. A header is sticky, so it can never be transparent — body rows would read through it
      // while scrolling. `plain` therefore paints the surface the table sits on (see
      // `plainSurfaceClass`).
      variant: {
        table: "border-b border-subtle bg-layer-1",
        spreadsheet: "border-e-[0.5px] border-b-[0.5px] border-subtle bg-layer-1 last:border-e-0",
        plain: cx("border-b border-subtle", plainSurfaceClass),
      },
      // Pin this header to an inline edge while the body scrolls sideways.
      pinned: {
        none: "z-20",
        start: cx(
          "sticky inset-s-0 z-30 border-e-[0.5px] border-subtle",
          pinnedOverflowShadowStart,
        ),
        end: cx("sticky inset-e-0 z-30 border-s-[0.5px] border-subtle", pinnedOverflowShadowEnd),
      },
      /** Column alignment. Pair it with the matching `align` on that column's cells. */
      align: {
        start: "text-start",
        center: "text-center",
        end: "text-end",
      },
      /**
       * Inline padding. `expand` pushes the label past the expand control of a column of
       * `TableExpandCell`s (the control's size plus one cell gap), so it lines up with the row
       * content instead of the chevron. The whole inline padding lives here so one padding pairing
       * is emitted per value.
       */
      inset: {
        none: "px-(--table-cell-padding-x)",
        expand: cx(
          "ps-[calc(var(--table-cell-padding-x)+var(--table-expand-size)+var(--table-cell-gap))]",
          "pe-(--table-cell-padding-x)",
        ),
      },
    },
    defaultVariants: tableHeadDefaultVariants,
  },
);

// A data cell (`<td>`). `variant` decides its borders; `pinned` makes it stick to an
// inline edge (carrying its own background so scrolled content does not show through).
const tableCellDefaultVariants = {
  pinned: "none",
  padding: "cell",
} as const;

// `min-w-11` is a 44px column floor, set by design on 2026-09-11 as an interim rule until adjustable
// column widths ship. It replaces the 140px minimum the Figma component frames declare, which the
// design's own composed example already contradicts with a 41px action column.
//
// Vertical padding is 8px, not the 12px Figma's component frame shows, and that is deliberate.
// A `<td>`'s height is a MINIMUM in table layout — the cell cannot clamp content taller than its
// box — so 12px padding only yields a 44px row while the tallest cell content stays inside the 20px
// slot Figma draws (44 − 12 − 12). Plane's real rows do not: a member row carries a 24px avatar.
// With 12px the row grew to 49px; with 8px the slot is 28px, the avatar fits, and `h-11` decides the
// height, so the row is 44px for every real surface. Design chose the literal 44px row over the
// literal 12px padding on 2026-09-15 (see F-34), knowing it moves the padding off Figma — F-02 had
// previously raised `table` from 8px to 12px, but on a 38px row, so this is not a revert of it.
export const tableCellVariants = cva("h-11 min-w-11 align-middle", {
  variants: {
    variant: {
      table: "border-b-[0.5px] border-subtle group-last/body-row:border-b-0",
      spreadsheet:
        "border-e-[0.5px] border-b-[0.5px] border-subtle group-last/body-row:border-b-0 last:border-e-0",
      // No frame closes the table off, so the last row keeps its hairline.
      plain: "border-b-[0.5px] border-subtle",
    },
    pinned: {
      none: "",
      start: cx(
        "sticky inset-s-0 z-10 border-e-[0.5px] border-subtle",
        pinnedRowTint,
        pinnedOverflowShadowStart,
      ),
      end: cx(
        "sticky inset-e-0 z-10 border-s-[0.5px] border-subtle",
        pinnedRowTint,
        pinnedOverflowShadowEnd,
      ),
    },
    // Cells that host a full-cell trigger (editable/action) drop their own padding so
    // the trigger fills the cell; plain cells keep the standard padding, now the same for both
    // looks — see the note above the cva for why the vertical half is 8px rather than Figma's 12px.
    padding: {
      cell: "px-(--table-cell-padding-x) py-2",
      trigger: "p-0",
    },
  },
  // A pinned cell's opaque resting fill follows its look: `layer-2` inside a frame, the host surface
  // for `plain`. It sits in compounds so each look emits one RESTING `bg-*`.
  //
  // It is not the only background utility on the cell: `pinnedRowTint` adds
  // `group-[[data-section]:not([data-selected])]/body-row:bg-layer-1` for a section row. That one
  // wins because its group selector is more specific than a bare utility, not because of source
  // order — so it must stay a group-scoped selector. Flattening it to an equal-specificity utility
  // would leave a pinned section cell to resolve by stylesheet order.
  compoundVariants: [
    { variant: framedVariants, pinned: ["start", "end"], class: "bg-layer-2" },
    { variant: "plain", pinned: ["start", "end"], class: plainSurfaceClass },
  ],
  // `variant` stays required — it is the look, and it arrives from context on the ready-mades. The
  // other two axes have an overwhelming common case, and making every cell in every table restate
  // it was the single loudest complaint from the Plane migration.
  defaultVariants: tableCellDefaultVariants,
});

// Per-axis types. `variant`/`pinned` are shared by head + cell — keep these unions in sync with
// both cvas above. `padding` is cell-only (from the cell cva). The `<Name>VariantProps` bundles
// stay PRIVATE — a part imports its own for `Props` (rule 10) and never re-exports it.
type TableCellVariantConfig = VariantProps<typeof tableCellVariants>;

/**
 * The table looks: `table` (framed, row dividers only), `spreadsheet` (framed, full grid) and
 * `plain` (no frame or fills, row dividers only).
 */
export type TableVariant = "table" | "spreadsheet" | "plain";

/** Which inline edge a header/cell pins to (or `none`) while the table scrolls sideways. */
export type TablePinned = "none" | "start" | "end";

/** A cell's inner spacing: `cell` pads the content; `trigger` drops it for a full-cell trigger. */
export type TableCellPadding = NonNullable<TableCellVariantConfig["padding"]>;

/**
 * A header's inline padding: `none` is the standard cell padding; `expand` clears an expand
 * control.
 */
export type TableHeadInset = "none" | "expand";

/** Column alignment, shared by a header and its cells. */
export type TableAlign = "start" | "center" | "end";

export type TableCellVariantProps = StrictVariantProps<
  typeof tableCellVariants,
  keyof typeof tableCellDefaultVariants
>;
export type TableHeadVariantProps = StrictVariantProps<
  typeof tableHeadVariants,
  keyof typeof tableHeadDefaultVariants
>;

// The inline flex layout inside a plain cell: leading slot, growing content, trailing
// slot. Padding lives on the `<td>` (`TableCell`), not here.
//
// The start padding is the nested-row indent: 24px per level, read from `--table-depth`, which
// `TableCellLayout` sets inline from its `depth` prop. A custom property rather than a cva axis so
// any depth works and tree data can pass its level straight through; with no depth it is 0.
export const tableCellLayoutVariants = cva(
  cx(
    "flex items-center gap-(--table-cell-gap) [--node-size:var(--control-glyph-md)]",
    "ps-[calc(var(--table-depth,0)*1.5rem)]",
  ),
);

// The expand control at the start of a `TableExpandCell`: a 16px button holding the smallest
// ladder glyph (14px), the same caret size as the header's sort slot. The
// `::before` box extends the pointer target to 24px (WCAG 2.5.8) without growing the painted
// control, so the row content keeps its alignment. It carries `group` so the shared
// `DisclosureIndicator` inside it can read `data-panel-open`.
export const tableExpandTriggerVariants = cva(
  cx(
    "group relative inline-flex size-(--table-expand-size) shrink-0 items-center justify-center rounded-sm outline-none [--node-size:var(--control-glyph-xs)]",
    "cursor-pointer hover:bg-layer-transparent-active",
    "focus-visible:ring-2 focus-visible:ring-accent-strong",
    "before:absolute before:-inset-1 before:content-['']",
  ),
);

// The empty box a row without children renders where the expand control would be, so every title
// in the column starts at the same edge.
export const tableExpandSpacerVariants = cva("size-(--table-expand-size) shrink-0");

const tableCellContentDefaultVariants = {
  align: "start",
} as const;

// The growing text region of a cell; truncates instead of overflowing. Alignment lives here rather
// than on the `<td>` because `TableCellLayout` is a flex row, and `text-align` on the cell does not
// move a flex child — it has to land on the growing region itself.
export const tableCellContentVariants = cva("min-w-0 flex-1 truncate", {
  variants: {
    align: {
      start: "text-start",
      center: "text-center",
      end: "text-end",
    },
  },
  defaultVariants: tableCellContentDefaultVariants,
});

export type TableCellContentVariantProps = StrictVariantProps<
  typeof tableCellContentVariants,
  keyof typeof tableCellContentDefaultVariants
>;

const tableHeadTitleDefaultVariants = {
  visibility: "visible",
} as const;

// The label region inside a `TableHead`: truncates the column title, or visually hides it for
// icon/action columns that still need an accessible header.
export const tableHeadTitleVariants = cva("min-w-0 flex-1 truncate", {
  variants: {
    visibility: {
      visible: "",
      hidden: "sr-only",
    },
  },
  defaultVariants: tableHeadTitleDefaultVariants,
});

type TableHeadTitleVariantConfig = VariantProps<typeof tableHeadTitleVariants>;
export type TableHeadTitleVisibility = NonNullable<TableHeadTitleVariantConfig["visibility"]>;
export type TableHeadTitleVariantProps = StrictVariantProps<
  typeof tableHeadTitleVariants,
  keyof typeof tableHeadTitleDefaultVariants
>;

// The sort control inside a sortable `TableHead`: a button that wraps the title + the
// sort indicator. The chevron sits to the inline-end of the text (an "always").
export const tableHeadSortTriggerVariants = cva(
  cx(
    "-mx-1 inline-flex w-full items-center justify-between gap-1.5 rounded-sm px-1 [--node-size:var(--control-glyph-xs)]",
    "text-tertiary hover:text-secondary",
    "outline-none focus-visible:ring-2 focus-visible:ring-accent-strong focus-visible:ring-inset",
    "cursor-pointer",
  ),
);

// The sort chevron at the trailing edge of a sort control. Figma draws this slot as a 20px rounded
// box on a transparent ground holding a 14px glyph, so the box is baked in here and the glyph is
// sized by the trigger's `--node-size`.
export const tableHeadSortIndicatorVariants = cva(
  cx(nodeSlotClass, "size-5 rounded-sm bg-layer-transparent px-1", "text-icon-secondary"),
);

const tableCellTriggerDefaultVariants = {
  selected: false,
} as const;

// The full-cell trigger inside an editable/action cell (rendered as the styled outer of
// a Base UI Menu trigger). `layout` picks the editable (text + trailing chevron) or
// action (centered icon) layout; `selected` keeps the active editable cell tinted.
// The box sits centred in an unpadded (`padding="trigger"`) select cell, filling the row so the
// pointer target is the whole 44px cell rather than the 16px box. It is a plain `<div>`, NOT a
// `<label>`: Base UI's checkbox walks up for an ancestor label and, finding one, assigns it an id
// and points the box at it with `aria-labelledby` — which outranks the `aria-label` the consumer
// passed, leaving the box with no accessible name at all.
export const tableSelectLayoutVariants = cva("flex h-full w-full items-center justify-center");

export const tableCellTriggerVariants = cva(
  cx(
    // 14px glyph, matching the header's sort slot and Figma's 20px box / 14px glyph pairing.
    "group/cell-trigger flex h-full min-h-11 w-full items-center outline-none [--node-size:var(--control-glyph-xs)]",
    "cursor-pointer bg-layer-transparent hover:bg-layer-transparent-hover focus-visible:bg-layer-transparent-hover",
    "focus-visible:ring-2 focus-visible:ring-accent-strong focus-visible:ring-inset",
    "data-popup-open:bg-layer-transparent-active",
    "disabled:pointer-events-none disabled:cursor-not-allowed disabled:text-disabled",
  ),
  {
    variants: {
      layout: {
        editable: "justify-between gap-1.5 px-3 text-start",
        action: "justify-center px-3",
      },
      selected: {
        true: "bg-layer-transparent-selected",
        false: "",
      },
    },
    defaultVariants: tableCellTriggerDefaultVariants,
  },
);

type TableCellTriggerVariantConfig = VariantProps<typeof tableCellTriggerVariants>;
/** `editable` lays out a value + trailing chevron; `action` centers an icon. */
export type TableCellTriggerLayout = NonNullable<TableCellTriggerVariantConfig["layout"]>;
export type TableCellTriggerVariantProps = StrictVariantProps<
  typeof tableCellTriggerVariants,
  keyof typeof tableCellTriggerDefaultVariants
>;

// The truncating value text inside an editable cell trigger.
export const tableCellTriggerLabelVariants = cva("min-w-0 truncate");

// The trailing glyph slot inside a cell trigger (the editable chevron, the action ellipsis). Same
// 20px box as the header's sort slot, per Figma, tinted and dimmed when the trigger is disabled.
export const tableCellTriggerIndicatorVariants = cva(
  cx(
    nodeSlotClass,
    "size-5 rounded-sm bg-layer-transparent px-1",
    "text-icon-secondary group-disabled/cell-trigger:text-icon-disabled",
  ),
);
