import { cva, cx, type VariantProps } from "class-variance-authority";

import { controlGroupClass, controlSize } from "../../internal/control-group";
import { controlInputClass } from "../../internal/control-input";
import { fieldControlSurfaceVariants } from "../../internal/field-control-surface";
import { checkboxItemIndicatorClass } from "../../internal/item-indicator";
import { listboxEmptyClass } from "../../internal/listbox-empty";
import {
  menuItemIndicatorClass,
  menuListPopupVariants,
  menuRowBaseClass,
  menuRowHighlightClass,
  menuRowPopupOpenHighlightClass,
  menuRowSingleClass,
  menuSeparatorClass,
  menuSubmenuRowVariantClasses,
} from "../../internal/menu-row-parts";
import { nodeSlotClass } from "../../internal/node-slot";
import { type StrictVariantProps } from "../../internal/variant-props";
import { pillVariants, type PillSize } from "../pill/variants";

export const comboboxListSpacerVariants = cva("relative w-full");
export const comboboxItemPositionerVariants = cva("absolute inset-x-0 top-0");

// Height, text, glyph, gap and radius ride the rung tokens; the side inset rides the field inset
// ladder (`--field-inset-*`), like the input frame.
const comboboxFrameSize = {
  md: cx(
    controlSize.md,
    "gap-(--control-gap-md) rounded-(--control-radius-md) px-(--field-inset-md)",
  ),
  lg: cx(
    controlSize.lg,
    "gap-(--control-gap-lg) rounded-(--control-radius-lg) px-(--field-inset-lg)",
  ),
  xl: cx(
    controlSize.xl,
    "gap-(--control-gap-xl) rounded-(--control-radius-xl) px-(--field-inset-xl)",
  ),
  "2xl": cx(
    controlSize["2xl"],
    "gap-(--control-gap-2xl) rounded-(--control-radius-2xl) px-(--field-inset-2xl)",
  ),
} as const;

const comboboxGhostFrameClass = cx(
  // Figma's ghost never paints a border or ring — open/focus and invalid both stay flat,
  // matching SelectTrigger ghost and IconToggle (`active:bg-layer-transparent-active`):
  // open/focused shows only the transparent-active fill; invalid shows only via the danger
  // helper text below, not the frame itself.
  "border border-transparent bg-layer-transparent",
  "hover:bg-layer-transparent-hover",
  "data-disabled:cursor-not-allowed data-disabled:border-transparent data-disabled:bg-transparent data-disabled:text-disabled data-disabled:hover:bg-transparent",
);

const comboboxInputGroupDefaultVariants = { variant: "secondary" } as const;

export const comboboxInputGroupVariants = cva(
  cx(
    // Wraps a separate focusable input → `group/control` so leading icons and the ghost open
    // fill can key off the inner control. A trailing control (clear/trigger renders a `<button>`)
    // sits flush: tighten the group's right padding so the chevron/clear glyph reads as part of
    // the input. The `:has()` selector outweighs the flat `px-*`, so it only applies when a
    // trailing control is present.
    // 288px (`min-w-72`) — the nearest scale step to Figma's 290px demonstrated width, floor only:
    // the frame still grows for longer content or a wider container (matches `SelectTrigger`'s own
    // fix for the identical 290px spec).
    "group/control flex min-w-72 items-center transition-[color,background-color,border-color,box-shadow]",
    "has-[button]:pr-1",
  ),
  {
    variants: {
      /**
       * Frame look. `secondary` is the bordered field surface; `ghost` is borderless and fills only
       * on hover / focus / open.
       */
      variant: {
        secondary: controlGroupClass,
        ghost: cx(
          comboboxGhostFrameClass,
          "focus-within:bg-layer-transparent-active",
          "has-[[data-popup-open]]:bg-layer-transparent-active",
          "has-[:disabled]:cursor-not-allowed has-[:disabled]:bg-transparent",
        ),
      },
      size: comboboxFrameSize,
    },
    defaultVariants: comboboxInputGroupDefaultVariants,
  },
);

export const comboboxInputVariants = cva(cx(controlInputClass, "flex-1"));

// Reserves the clear control's own footprint: Base UI's `Clear` is grafted with `keepMounted`
// (never unmounted) and only turns invisible at an empty value, so this slot's width always tracks
// the real rendered child instead of a guessed size step.
export const comboboxInputGroupClearVariants = cva("shrink-0 [&>*:not([data-visible])]:invisible");
export type ComboboxInputGroupClearVariantProps = StrictVariantProps<
  typeof comboboxInputGroupClearVariants
>;

// Figma "Prominence", the same vocabulary as `SelectTrigger`: `secondary` is the bordered field
// surface, `ghost` drops the border and fill, and `pill` keeps bordered chrome but hugs its value
// for compact property/filter pickers.
const comboboxTriggerDefaultVariants = { variant: "secondary", width: "auto" } as const;

/**
 * The closed-field trigger: a focusable button (not a filter input). Same geometry as
 * `ComboboxInputGroup`, but `focus-visible` keys off this element — it IS the control, like
 * `SelectTrigger`.
 */
export const comboboxTriggerVariants = cva(
  cx(
    "group/control items-center text-start outline-none",
    "transition-[color,background-color,border-color,box-shadow]",
  ),
  {
    variants: {
      /**
       * Frame look. `secondary` is the bordered field surface; `ghost` is borderless and fills only
       * on hover / focus / open; `pill` is the outline Pill chrome, hugging its value.
       */
      variant: {
        secondary: cx(
          // 288px (`min-w-72`) — the nearest scale step to Figma's 290px demonstrated width, floor
          // only (matches `ComboboxInputGroup`/`ComboboxChips` and `SelectTrigger`'s own fix for
          // the same spec).
          "flex text-primary data-placeholder:text-placeholder",
          fieldControlSurfaceVariants({ focus: "visible" }),
          "hover:border-strong hover:bg-layer-2-hover",
          // Focus moves into the list once the popup opens, so the open frame keys off
          // `data-popup-open` to keep the accent border and ring Figma draws for "selected".
          "data-popup-open:border-accent-strong data-popup-open:ring-2 data-popup-open:ring-accent-strong/20",
          "data-invalid:data-popup-open:border-danger-strong data-invalid:data-popup-open:ring-danger-strong/20",
          "data-disabled:cursor-not-allowed data-disabled:border-subtle-1 data-disabled:bg-layer-2 data-disabled:text-disabled data-disabled:ring-0 data-disabled:hover:border-subtle-1 data-disabled:hover:bg-layer-2",
        ),
        ghost: cx(
          "flex text-primary data-placeholder:text-placeholder",
          comboboxGhostFrameClass,
          "focus-visible:bg-layer-transparent-active",
          "data-popup-open:bg-layer-transparent-active",
        ),
        pill: cx(
          // The complete outline Pill chrome and size geometry are composed below per size, the
          // same as `SelectTrigger`'s pill. Keep only the combobox-specific invalid state here.
          "data-invalid:border-danger-strong data-invalid:focus-visible:ring-danger-strong",
          "data-invalid:data-popup-open:border-danger-strong data-invalid:data-popup-open:ring-2 data-invalid:data-popup-open:ring-danger-strong",
        ),
      },
      // The cva holds both size families; the compound variants below keep each family's geometry
      // on its own variants, and the public props enforce the same pairing.
      size: { xs: "", sm: "", md: "", lg: "", xl: "", "2xl": "" },
      // Width is independent from field prominence. `auto` preserves the established 288px floor;
      // `fit` opts into intrinsic content width. Public props keep this axis off the pill branch.
      width: {
        auto: "",
        fit: "",
      },
    },
    compoundVariants: [
      { variant: ["secondary", "ghost"], width: "auto", class: "min-w-72" },
      { variant: ["secondary", "ghost"], width: "fit", class: "w-fit min-w-0" },
      { variant: ["secondary", "ghost"], size: "md", class: comboboxFrameSize.md },
      { variant: ["secondary", "ghost"], size: "lg", class: comboboxFrameSize.lg },
      { variant: ["secondary", "ghost"], size: "xl", class: comboboxFrameSize.xl },
      { variant: ["secondary", "ghost"], size: "2xl", class: comboboxFrameSize["2xl"] },
      { variant: "pill", size: "xs", class: pillVariants({ size: "xs", variant: "outline" }) },
      { variant: "pill", size: "sm", class: pillVariants({ size: "sm", variant: "outline" }) },
      { variant: "pill", size: "md", class: pillVariants({ size: "md", variant: "outline" }) },
    ],
    defaultVariants: comboboxTriggerDefaultVariants,
  },
);

/** Selected-value (or placeholder) label inside `ComboboxTrigger`. */
// `min-w-[6ch]` keeps a few preview characters visible beside a long overflow summary in a
// narrow frame (flex-1 basis is 0; without a floor the count can claim the full row width).
export const comboboxValueVariants = cva("min-w-[6ch] flex-1 truncate");

/** Keep the remaining-selection count visible beside a truncated value preview. */
export const comboboxValueOverflowVariants = cva("min-w-0 truncate");

const comboboxChipsDefaultVariants = { variant: "secondary" } as const;

// The multiselect variant of the input frame. Same geometry as `ComboboxInputGroup` so chips sit
// in the field's own padding rather than a tighter inset well.
export const comboboxChipsVariants = cva(
  cx(
    // 288px (`min-w-72`) — see `ComboboxInputGroup`'s identical comment above.
    "group/control flex min-w-72 items-center transition-[color,background-color,border-color,box-shadow]",
    // `py-1` is the chips' vertical inset. It never changes the single-row height — every rung is
    // exactly chip + 8px (md 20+8=28, lg 24+8=32, xl 28+8=36, 2xl 32+8=40), so `min-h` still
    // governs — but under the default `layout="wrap"` it is what keeps a second row of chips off
    // the frame's top and bottom border.
    "py-1",
    // DIRECT child only. Unlike `ComboboxInputGroup`, this frame always contains `<button>`
    // descendants — `ComboboxChip`'s `remove` control is required and is an `IconButton` — so a
    // bare `has-[button]` would match as soon as one chip exists and, at 0,2,0, outrank the
    // `px-(--field-inset-*)` from `comboboxFrameSize`: right padding would drop to 4px while
    // the left stayed 12px, then snap back when the last chip was removed. The trailing control
    // this rule exists to hug (`BaseCombobox.Trigger`) is a direct child; chips' remove buttons are
    // grandchildren.
    "has-[>button]:pr-1",
  ),
  {
    variants: {
      /**
       * Frame look. `secondary` is the bordered field surface; `ghost` is borderless and fills only
       * on hover / focus / open.
       */
      variant: {
        secondary: controlGroupClass,
        ghost: cx(
          comboboxGhostFrameClass,
          "focus-within:bg-layer-transparent-active",
          "has-[[data-popup-open]]:bg-layer-transparent-active",
          "has-[:disabled]:cursor-not-allowed has-[:disabled]:bg-transparent",
        ),
      },
      size: comboboxFrameSize,
      // `wrap` grows onto new rows; the ready-made uses it so its bounded chip preview still
      // leaves room for the input. `collapse` is a single clipped row for custom compositions
      // whose caller controls fitting. The primitive requires an explicit layout.
      layout: {
        wrap: "flex-wrap",
        collapse: "flex-nowrap overflow-hidden",
      },
    },
    defaultVariants: comboboxChipsDefaultVariants,
  },
);

// One selected value, rendered as a removable pill (the outline pill chrome). Arrow keys move
// focus onto a chip, so it carries the standard focus ring. `--node-size` sizes an optional
// leading/trailing `Icon`/avatar slot (composed by the ready-made) to match the chip text.
//
// The chip fills the frame's inner height — the frame is `controlSize` — and the text follows
// that height the way it does on every other chip in the library. Max width and ellipsis match
// the Figma Pill cap.
export const comboboxChipVariants = cva(
  cx(
    "flex max-w-[150px] min-w-0 shrink-0 cursor-default items-center gap-1 overflow-hidden rounded-sm border-sm border-subtle-1 bg-layer-2 ps-1.5 pe-0.5 text-secondary",
    "outline-none focus-visible:ring-2 focus-visible:ring-accent-strong",
    "data-disabled:cursor-not-allowed data-disabled:border-subtle-1 data-disabled:text-disabled",
  ),
  {
    variants: {
      size: {
        // 20px painted, 24px pointer target via the `::before` ring (WCAG 2.5.8). Adjacent
        // chips sit 4px apart, so neighboring rings touch but never intersect — which keeps
        // the undersized-target spacing exception intact.
        xs: "relative h-(--control-height-xs) text-caption-md-regular [--node-size:var(--control-glyph-xs)] before:absolute before:-inset-0.5 before:-z-10 before:content-['']",
        sm: "h-(--control-height-sm) text-body-xs-regular [--node-size:var(--control-glyph-sm)]",
        md: "h-(--control-height-md) text-body-xs-regular [--node-size:var(--control-glyph-md)]",
        lg: "h-(--control-height-lg) text-body-sm-regular [--node-size:var(--control-glyph-lg)]",
      },
    },
  },
);

// The "+N more" count shown after the visible chips when selection exceeds `maxVisible`.
// Placeholder-colored, non-interactive caption sized to the chip
// text; the hidden values are managed from the popup (deselect to remove).
export const comboboxChipOverflowVariants = cva(
  // `shrink-0` is load-bearing, not decoration. In `layout="collapse"` the frame is
  // `flex-nowrap overflow-hidden` and the chips are `shrink-0 max-w-[150px]`, so this count and the
  // input are the only shrinkable items — as `flex-1 min-w-0` the count collapsed to an ellipsis
  // exactly when it was needed (two ~125px chips already fill a 288px frame), losing the affordance
  // `maxVisible` exists to provide. `truncate` stays for a pathological `overflowLabel`.
  // `tabular-nums` keeps digit width stable when the count ticks (e.g. +997 → +996) so a wrap-layout
  // chip frame does not reflow the inline input by ~1px and trip a ResizeObserver loop warning.
  "shrink-0 truncate text-placeholder tabular-nums select-none",
  {
    variants: {
      size: {
        xs: "text-caption-md-regular",
        sm: "text-body-xs-regular",
        md: "text-body-xs-regular",
        lg: "text-body-sm-regular",
      },
    },
  },
);

/** Popup: shared raised/flat list surface (see `internal/menu-row-parts`). */
export const comboboxPopupVariants = menuListPopupVariants;

const comboboxItemDefaultVariants = { variant: "neutral" } as const;

/** Option row: the shared menu-row chrome so the combobox list matches the dropdown panel. */
export const comboboxItemVariants = cva(
  cx(
    menuRowBaseClass,
    menuRowSingleClass,
    menuRowHighlightClass,
    // Reset native `<button>` chrome when a row is rendered as a button. Harmless on the default
    // `<div>` option rows. No `font-inherit`: the family namespace is reset
    // (`styles/variables.css`, `--font-*: initial`) so only `font-heading` / `font-body` /
    // `font-code` resolve — `font-inherit` compiled to nothing. Preflight already applies
    // `font: inherit` to `button`, which is what actually does this job.
    "border-0 bg-transparent py-0 text-start",
  ),
  {
    variants: {
      /**
       * Row look. `neutral` is the standard text hierarchy, `accent` marks the primary action, and
       * `danger` marks a destructive one.
       */
      variant: {
        neutral: "text-primary",
        accent:
          "text-accent-primary data-disabled:text-disabled data-highlighted:text-accent-primary",
        danger:
          "text-danger-primary data-disabled:text-disabled data-highlighted:text-danger-primary",
      },
    },
    defaultVariants: comboboxItemDefaultVariants,
  },
);

/**
 * The sticky "Select all" row (`ComboboxSelectAll`): the option row's chrome on a `<button>`, with
 * its own hover fill. Option rows light up off `data-highlighted`, which Base UI sets only on real
 * options — never on this button — so the fill is keyed to `:hover` here, on this row alone, rather
 * than on the shared option row (where any button-rendered row would then show both fills). A
 * disabled row takes no hover: `menuRowBaseClass` drops its pointer events off `data-disabled`.
 */
export const comboboxSelectAllVariants = cva(
  cx(
    menuRowBaseClass,
    menuRowSingleClass,
    "border-0 bg-transparent py-0 text-start text-primary hover:bg-layer-transparent-hover",
  ),
);

const comboboxSubmenuTriggerDefaultVariants = { variant: "neutral" } as const;

/**
 * Submenu-trigger row: the same menu-row chrome as `comboboxItemVariants`, plus the
 * `data-popup-open` highlight that keeps the row lit while its nested list is open beside it. The
 * look palette is `menuSubmenuRowVariantClasses` rather than the option row's own, so an
 * accent/danger submenu row holds its text colour while open (shared with `MenuSubmenuTrigger`).
 */
export const comboboxSubmenuTriggerVariants = cva(
  cx(
    menuRowBaseClass,
    menuRowSingleClass,
    menuRowHighlightClass,
    menuRowPopupOpenHighlightClass,
    // Same `<button>` chrome reset as the option row — a submenu trigger is a `<div>` option by
    // default, but stays renderable as a button.
    "border-0 bg-transparent py-0 text-start",
  ),
  {
    variants: {
      /**
       * Row look. `neutral` is the standard text hierarchy, `accent` marks the primary action, and
       * `danger` marks a destructive one.
       */
      variant: menuSubmenuRowVariantClasses,
    },
    defaultVariants: comboboxSubmenuTriggerDefaultVariants,
  },
);

export const comboboxItemContentVariants = cva("flex min-w-0 flex-1 flex-col gap-1");

export const comboboxItemTitleVariants = cva("truncate");

export const comboboxItemTrailingVariants = cva(nodeSlotClass);

export const comboboxItemControlVariants = cva("flex shrink-0 items-center");

/** Trailing single-select check gutter — shared `menuItemIndicatorClass`. */
export const comboboxItemIndicatorVariants = cva(menuItemIndicatorClass);

/**
 * Checkbox-row indicator: the leading checkbox BOX of a multi-select row — shared
 * `checkboxItemIndicatorClass`, the same box a multiple `Select` row draws.
 */
export const comboboxCheckboxItemIndicatorVariants = cva(checkboxItemIndicatorClass);

export const comboboxEmptyVariants = cva(listboxEmptyClass);

export const comboboxSeparatorVariants = cva(menuSeparatorClass);

/**
 * Same `p-1` inset as a flat `ComboboxPopup`, for sticky rows that sit in the overlay header
 * (Select all + separator). Without this, those rows sit flush under Search's border while the
 * separator's `my-1` still adds space below — the checkbox reads top-heavy. The inset matches the
 * scrolling list so the divider's `-mx-1` still reaches the panel edge.
 */
export const comboboxStickyListVariants = cva("p-1");

/**
 * Search: the sticky search row pinned above the popup list. No fill: it shows the panel surface
 * through.
 */
export const comboboxSearchVariants = cva(
  "flex shrink-0 items-center gap-1.5 border-b border-subtle px-3 py-2",
);

/**
 * Search input: the borderless text field in `ComboboxSearch`. Carries the same type and colour as
 * the rows it filters.
 */
export const comboboxSearchInputVariants = cva(
  "min-w-0 flex-1 bg-transparent text-body-xs-regular text-primary outline-none placeholder:text-placeholder",
);

export type ComboboxInputGroupVariantProps = StrictVariantProps<
  typeof comboboxInputGroupVariants,
  keyof typeof comboboxInputGroupDefaultVariants
>;
export type ComboboxChipsVariantProps = StrictVariantProps<
  typeof comboboxChipsVariants,
  keyof typeof comboboxChipsDefaultVariants
>;
export type ComboboxChipVariantProps = StrictVariantProps<typeof comboboxChipVariants>;
export type ComboboxChipOverflowVariantProps = StrictVariantProps<
  typeof comboboxChipOverflowVariants
>;
export type ComboboxItemVariantProps = StrictVariantProps<
  typeof comboboxItemVariants,
  keyof typeof comboboxItemDefaultVariants
>;
export type ComboboxSubmenuTriggerVariantProps = StrictVariantProps<
  typeof comboboxSubmenuTriggerVariants,
  keyof typeof comboboxSubmenuTriggerDefaultVariants
>;
export type ComboboxPopupVariantProps = StrictVariantProps<typeof comboboxPopupVariants>;

type ComboboxInputGroupVariantConfig = ComboboxInputGroupVariantProps;
export type ComboboxSize = ComboboxInputGroupVariantConfig["size"];
export type ComboboxVariant = NonNullable<ComboboxInputGroupVariantConfig["variant"]>;

type ComboboxTriggerVariantConfig = VariantProps<typeof comboboxTriggerVariants>;

/** Every size accepted across all Combobox trigger variants. */
export type ComboboxTriggerAnySize = NonNullable<ComboboxTriggerVariantConfig["size"]>;

/** The trigger's look: the frame looks (`secondary`, `ghost`) plus `pill`. */
export type ComboboxTriggerVariant = NonNullable<ComboboxTriggerVariantConfig["variant"]>;

/** How a field-style Combobox trigger calculates its inline width. */
export type ComboboxTriggerWidth = NonNullable<ComboboxTriggerVariantConfig["width"]>;

export type ComboboxTriggerPillSize = Extract<ComboboxTriggerAnySize, PillSize>;

/** Pill and field-style triggers take different size scales, like `SelectTrigger`. */
export type ComboboxTriggerVariantProps =
  | {
      /** Trigger size on Pill's scale: `xs`, `sm` or `md`. */
      size: ComboboxTriggerPillSize;
      /** `pill` hugs its value with outline Pill chrome and shows no automatic chevron. */
      variant: "pill";
      width?: never;
    }
  | {
      /** Trigger size, from `md` to `2xl`: height, text and glyph sizing. */
      size: ComboboxSize;
      /**
       * Frame look. `secondary` is the bordered field surface; `ghost` is borderless. Invalid on
       * ghost has no trigger chrome — the danger cue is the helper text below.
       *
       * @default "secondary"
       */
      variant?: ComboboxVariant;
      /** `auto` keeps the 288px minimum; `fit` hugs the rendered trigger content. */
      width?: ComboboxTriggerWidth;
    };

export type ComboboxChipSize = NonNullable<ComboboxChipVariantProps["size"]>;
export type ComboboxChipOverflowSize = NonNullable<ComboboxChipOverflowVariantProps["size"]>;

type ComboboxItemVariantConfig = ComboboxItemVariantProps;
export type ComboboxItemVariant = NonNullable<ComboboxItemVariantConfig["variant"]>;

type ComboboxSubmenuTriggerVariantConfig = ComboboxSubmenuTriggerVariantProps;
export type ComboboxSubmenuTriggerVariant = NonNullable<
  ComboboxSubmenuTriggerVariantConfig["variant"]
>;

type ComboboxPopupVariantConfig = ComboboxPopupVariantProps;
export type ComboboxPopupElevation = NonNullable<ComboboxPopupVariantConfig["elevation"]>;
