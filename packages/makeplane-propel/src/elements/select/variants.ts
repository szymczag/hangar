import { cva, cx, type VariantProps } from "class-variance-authority";

import { controlSize } from "../../internal/control-group";
import { fieldControlSurfaceVariants } from "../../internal/field-control-surface";
import { checkboxItemIndicatorClass } from "../../internal/item-indicator";
import {
  menuFooterClass,
  menuItemContentClass,
  menuItemDescriptionClass,
  menuItemIndicatorClass,
  menuItemSecondaryTextClass,
  menuItemTitleRowClass,
  menuRowBaseClass,
  menuRowHighlightClass,
  menuRowSingleHeightClass,
  menuRowStackedHeightClass,
  menuSeparatorClass,
} from "../../internal/menu-row-parts";
import { nodeSlotClass } from "../../internal/node-slot";
import { type StrictVariantProps } from "../../internal/variant-props";
import { pillVariants, type PillSize } from "../pill/variants";

// The field region that stacks the label over the trigger as a column. Holds the
// gap between `SelectLabel` and `SelectTrigger`; sizes to its widest child.
export const selectFieldVariants = cva("flex w-fit flex-col gap-1.5");

// The visible label above the trigger. Steps with the trigger's own size axis so a hand-composed
// select never pairs a 14px value with a 13px label: the `lg` trigger (32px, body-sm) takes the
// 13px label every field wrapper uses at its smallest rung, and the `xl`/`2xl` triggers (36/40px,
// body-sm/body-md) take the 14px label `FieldLabel` renders at the same control height.
export const selectLabelVariants = cva("text-primary", {
  variants: {
    size: {
      md: "text-body-xs-medium",
      lg: "text-body-xs-medium",
      xl: "text-body-sm-medium",
      "2xl": "text-body-sm-medium",
    },
  },
});

// Figma "Prominence": `secondary` is the bordered `layer-2` field surface (matches IconToggle's own
// secondary/ghost vocabulary for the same raised-vs-transparent look); `ghost` drops the border and
// fill for a trigger that sits directly on its parent surface (e.g. inline in a toolbar row); `pill`
// keeps bordered chrome but hugs its value for compact property/filter selectors.
export const selectTriggerDefaultVariants = { variant: "secondary", width: "auto" } as const;

// The trigger wraps its selected value and optional glyphs in a single row. Height, text size, and
// icon size track the size axis (Figma "Size").
export const selectTriggerVariants = cva(
  cx(
    "group/control items-center outline-none",
    // `group/control` is the name Icon's `placeholder`/`secondary` tints read for focus-brighten
    // and disabled-dim (same contract Combobox/Input get via `controlGroupClass`). Only the group
    // name — not the rest of `controlGroupClass`, which would re-apply the bordered surface onto
    // ghost. Mirror `controlGroupClass`'s `data-disabled` guards: `:hover` still matches a disabled
    // trigger, so without these the rest hover paints on a control that should read flat.
    "data-disabled:cursor-not-allowed data-disabled:text-disabled data-disabled:ring-0",
  ),
  {
    variants: {
      // Figma "Prominence" axis.
      variant: {
        secondary: cx(
          // 288px (`min-w-72`) is the nearest scale step to Figma's 290px demonstrated field
          // width. It is a floor only; the trigger can still grow with content or its container.
          // The trigger is itself the focusable element → `focus: visible`. Open shows the same
          // accent border + ring: focus moves into the list, so `:focus-visible` alone would leave
          // the trigger looking closed.
          fieldControlSurfaceVariants({ focus: "visible" }),
          "flex cursor-default justify-between text-primary",
          "data-popup-open:border-accent-strong data-popup-open:ring-2 data-popup-open:ring-accent-strong/20",
          "data-invalid:data-popup-open:border-danger-strong data-invalid:data-popup-open:ring-danger-strong/20",
          "hover:border-strong hover:bg-layer-2-hover",
          "data-disabled:border-subtle-1 data-disabled:bg-layer-2 data-disabled:hover:border-subtle-1 data-disabled:hover:bg-layer-2",
        ),
        ghost: cx(
          // Figma's ghost never paints a border or ring — open/focus and invalid both stay flat,
          // matching `IconToggle`'s own ghost precedent (`active:bg-layer-transparent-active`):
          // open/focused shows only the transparent-active fill; invalid shows only via the danger
          // helper text below, not the trigger itself. Open is `data-popup-open` (focus often
          // moves into the list, so `:focus-visible` alone would leave the trigger looking closed).
          "flex cursor-default justify-between border border-transparent bg-layer-transparent text-primary",
          "focus-visible:bg-layer-transparent-active data-popup-open:bg-layer-transparent-active",
          "hover:bg-layer-transparent-hover",
          "data-disabled:border-transparent data-disabled:bg-transparent data-disabled:hover:bg-transparent",
        ),
        pill: cx(
          // The complete outline Pill chrome and size geometry are composed below per size. Keep
          // only Select-specific invalid state rules here.
          "data-invalid:border-danger-strong data-invalid:focus-visible:ring-danger-strong",
          "data-invalid:data-popup-open:border-danger-strong data-invalid:data-popup-open:ring-2 data-invalid:data-popup-open:ring-danger-strong",
        ),
      },
      // The CVA contains both size families; compound variants below keep each family's geometry
      // scoped to its compatible prominence. Public props enforce the same relationship.
      size: {
        xs: "",
        sm: "",
        md: "",
        lg: "",
        xl: "",
        "2xl": "",
      },
      // Width is independent from field prominence. `auto` preserves the established 288px floor;
      // `fit` opts into intrinsic content width. Public props keep this axis off the pill branch.
      width: {
        auto: "",
        fit: "",
      },
    },
    compoundVariants: [
      {
        variant: ["secondary", "ghost"],
        width: "auto",
        class: "min-w-72",
      },
      {
        variant: ["secondary", "ghost"],
        width: "fit",
        class: "w-fit min-w-0",
      },
      {
        variant: ["secondary", "ghost"],
        size: "md",
        class: cx(
          controlSize.md,
          "gap-(--control-gap-md) rounded-(--control-radius-md) px-(--field-inset-md)",
        ),
      },
      {
        variant: ["secondary", "ghost"],
        size: "lg",
        class: cx(
          controlSize.lg,
          "gap-(--control-gap-lg) rounded-(--control-radius-lg) px-(--field-inset-lg)",
        ),
      },
      {
        variant: ["secondary", "ghost"],
        size: "xl",
        class: cx(
          controlSize.xl,
          "gap-(--control-gap-xl) rounded-(--control-radius-xl) px-(--field-inset-xl)",
        ),
      },
      {
        variant: ["secondary", "ghost"],
        size: "2xl",
        class: cx(
          controlSize["2xl"],
          "gap-(--control-gap-2xl) rounded-(--control-radius-2xl) px-(--field-inset-2xl)",
        ),
      },
      { variant: "pill", size: "xs", class: pillVariants({ size: "xs", variant: "outline" }) },
      { variant: "pill", size: "sm", class: pillVariants({ size: "sm", variant: "outline" }) },
      { variant: "pill", size: "md", class: pillVariants({ size: "md", variant: "outline" }) },
    ],
    defaultVariants: selectTriggerDefaultVariants,
  },
);

// The list inside the popup panel (Base UI's `Select.List`): the rows' `p-1` inset, the same one
// the Combobox and Menu lists sit at inside their panels. The panel's `ScrollArea` does the
// scrolling.
export const selectListVariants = cva("p-1 outline-none");

// The option row: the shared menu-row chrome, so a select list matches the Combobox and Menu
// panels — the same 32px row, type, glyph `--node-size` and highlight. The row does not ramp with
// the trigger (the popup rows stay one height across every trigger size, per Figma).
const selectItemDefaultVariants = { layout: "single" } as const;

export const selectItemVariants = cva(
  cx(menuRowBaseClass, menuRowHighlightClass, "cursor-default text-primary"),
  {
    variants: {
      /**
       * How the row arranges its text. `single` is a one-line, vertically centered row; `stacked`
       * grows to fit a description beneath the title and top-aligns the row's leading content.
       */
      layout: {
        single: menuRowSingleHeightClass,
        // The shared stacked rule centres the node right before the text column (the icon) on the
        // title line; a `multiple` row's checkbox leads the row ahead of it, so it takes the same
        // nudge as the row's first child.
        stacked: cx(
          menuRowStackedHeightClass,
          "[&>:first-child:not([data-slot=menu-item-content])]:mt-0.5",
        ),
      },
    },
    defaultVariants: selectItemDefaultVariants,
  },
);

// The sticky "Select all" row (`SelectSelectAll`): the option row's chrome on a `<button>`, with
// its own hover fill. Option rows light up off `data-highlighted`, which Base UI sets only on real
// options — never on this button — so the fill is keyed to `:hover` here, on this row alone, rather
// than on the shared option row (where any button-rendered row would then show both fills).
// `text-start` undoes the button's native centering. A disabled row takes no hover:
// `menuRowBaseClass` drops its pointer events off `data-disabled`.
export const selectSelectAllVariants = cva(
  cx(
    menuRowBaseClass,
    menuRowSingleHeightClass,
    "cursor-default text-start text-primary hover:bg-layer-transparent-hover",
  ),
);

// The text column of a row: grows to fill it (so the check and trailing nodes sit at the
// inline-end) and stacks the title row over an optional description.
export const selectItemContentVariants = cva(menuItemContentClass);

// The baseline-aligned row holding the label and any inline secondary text.
export const selectItemTitleRowVariants = cva(menuItemTitleRowClass);

// The option's label (Base UI's `Select.ItemText`). Truncates rather than wrapping.
export const selectItemTextVariants = cva("truncate");

// Muted text shown inline after the label.
export const selectItemSecondaryTextVariants = cva(menuItemSecondaryTextClass);

// A muted second line beneath the label (the option's description).
export const selectItemDescriptionVariants = cva(menuItemDescriptionClass);

// A slot at the row's inline-end for arbitrary content (a count, a badge). Sizes an icon child to
// the row's `--node-size`; adds no tint.
export const selectItemTrailingVariants = cva(nodeSlotClass);

// A thin divider between groups of options — the shared menu separator.
export const selectSeparatorVariants = cva(menuSeparatorClass);

// The same `p-1` inset as the scrolling list, for sticky rows in the panel header (a Select all row
// + separator), so they line up with the options below.
export const selectStickyListVariants = cva("p-1");

// A non-interactive footer pinned below the list — the shared menu footer.
export const selectFooterVariants = cva(menuFooterClass);

// The single-select check: the shared trailing check gutter. Its fixed `w-4` reserves the column
// on unselected rows too (the graft passes `keepMounted`), so toggling a selection never
// re-truncates a label.
export const selectItemIndicatorVariants = cva(menuItemIndicatorClass);

// The multi-select marker: the leading checkbox box a `multiple` select row draws in place of the
// trailing check — the shared `checkboxItemIndicatorClass`, identical to Combobox's.
export const selectCheckboxItemIndicatorVariants = cva(checkboxItemIndicatorClass);

// The trigger's single-line value text. `flex-1 min-w-0` (Figma's own `flex-[1_0_0] min-w-px`)
// lets it grow to fill the row and shrink to truncate — without `flex-1`, a field trigger's
// `justify-between` only looks correct by accident when there are exactly two children (value +
// chevron); adding a leading icon makes justify-content distribute the extra space as a gap before
// the value instead of after it, pushing the text toward the middle of the box. `text-start`
// overrides the browser's default `text-align: center` on `<button>` (inherited by this span),
// which otherwise centers the value text inside its own flex-1 box regardless of the fix above.
// `truncate` keeps it on one line per the Figma spec — matching `PillLabel`/`ToggleLabel`'s own
// single-line-label treatment — instead of wrapping and growing the trigger past its fixed
// control height.
// `data-placeholder` is what Base UI's `Select.Value` sets while nothing is selected.
export const selectValueVariants = cva(
  "min-w-0 flex-1 truncate text-start data-placeholder:text-placeholder",
);

type SelectTriggerVariantConfig = VariantProps<typeof selectTriggerVariants>;

/** Every size accepted across all Select trigger variants. */
export type SelectTriggerAnySize = NonNullable<SelectTriggerVariantConfig["size"]>;

export type SelectTriggerVariant = NonNullable<SelectTriggerVariantConfig["variant"]>;

/** How a field-style Select trigger calculates its inline width. */
export type SelectTriggerWidth = NonNullable<SelectTriggerVariantConfig["width"]>;

export type SelectTriggerPillSize = Extract<SelectTriggerAnySize, PillSize>;

/** The established field-style Select size scale, kept stable for existing consumers. */
export type SelectTriggerSize = Extract<SelectTriggerAnySize, "md" | "lg" | "xl" | "2xl">;

export type SelectTriggerFieldSize = SelectTriggerSize;

/** Pill and field-style Select triggers intentionally expose different size scales. */
export type SelectTriggerVariantProps =
  | { size: SelectTriggerPillSize; variant: "pill"; width?: never }
  | {
      size: SelectTriggerFieldSize;
      variant?: Exclude<SelectTriggerVariant, "pill">;
      /** `auto` keeps the 288px minimum; `fit` hugs the rendered trigger content. */
      width?: SelectTriggerWidth;
    };

export type SelectLabelSize = NonNullable<VariantProps<typeof selectLabelVariants>["size"]>;

export type SelectLabelVariantProps = StrictVariantProps<typeof selectLabelVariants>;

export type SelectItemVariantProps = StrictVariantProps<
  typeof selectItemVariants,
  keyof typeof selectItemDefaultVariants
>;

export type SelectItemLayout = NonNullable<VariantProps<typeof selectItemVariants>["layout"]>;
