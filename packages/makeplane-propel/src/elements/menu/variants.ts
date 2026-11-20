import { cva, cx, type VariantProps } from "class-variance-authority";

import {
  menuCheckboxItemIndicatorClass,
  menuFooterClass,
  menuItemContentClass,
  menuItemDescriptionClass,
  menuItemIndicatorClass,
  menuItemSecondaryTextClass,
  menuItemTitleRowClass,
  menuListPopupVariants,
  menuRadioItemCheckClass,
  menuRadioItemIndicatorClass,
  menuRowBaseClass,
  menuRowHighlightClass,
  menuRowPopupOpenHighlightClass,
  menuRowSingleClass,
  menuRowSingleHeightClass,
  menuRowStackedHeightClass,
  menuRowVariantClasses,
  menuSeparatorClass,
  menuSubmenuRowVariantClasses,
} from "../../internal/menu-row-parts";
import { nodeSlotClass } from "../../internal/node-slot";
import { type StrictVariantProps } from "../../internal/variant-props";

/** Popup: shared raised/flat list surface (see `internal/menu-row-parts`). */
export const menuPopupVariants = menuListPopupVariants;

const menuRowDefaultVariants = {
  variant: "neutral",
} as const;

/** Standalone `MenuItem` row: `layout` (single-line vs stacked) + `variant`. */
export const menuRowVariants = cva(cx(menuRowBaseClass, menuRowHighlightClass), {
  variants: {
    /**
     * How the row arranges its text. `single` is a one-line, vertically centered row; `stacked`
     * grows to fit a description beneath the title and top-aligns the row's leading content.
     */
    layout: {
      single: menuRowSingleHeightClass,
      stacked: menuRowStackedHeightClass,
    },
    /**
     * Row look. `neutral` is the standard text hierarchy, `accent` marks the primary action, and
     * `danger` marks a destructive one.
     */
    variant: menuRowVariantClasses,
  },
  defaultVariants: menuRowDefaultVariants,
});

/**
 * CheckboxItem row: the shared row base, fixed to the single-line/default-emphasis pairing (a
 * checkbox row never carries a description).
 */
export const menuCheckboxItemVariants = cva(
  cx(menuRowBaseClass, menuRowSingleClass, menuRowHighlightClass),
  {
    variants: {
      /**
       * Row look. `neutral` is the standard text hierarchy, `accent` marks the primary action, and
       * `danger` marks a destructive one.
       */
      variant: menuRowVariantClasses,
    },
    defaultVariants: menuRowDefaultVariants,
  },
);

/**
 * SubmenuTrigger row: the shared row base; also highlights while its submenu popup is open
 * (`data-popup-open`).
 */
export const menuSubmenuTriggerVariants = cva(
  cx(menuRowBaseClass, menuRowSingleClass, menuRowHighlightClass, menuRowPopupOpenHighlightClass),
  {
    variants: {
      /**
       * Row look. `neutral` is the standard text hierarchy, `accent` marks the primary action, and
       * `danger` marks a destructive one.
       */
      variant: menuSubmenuRowVariantClasses,
    },
    defaultVariants: menuRowDefaultVariants,
  },
);

/**
 * The text column of a row. Grows to fill the row (so trailing nodes/indicators sit at the
 * inline-end), stacks the title row over an optional description, and clips overflow.
 *
 * `gap-1` is the declared space between the title and a description. Without it the two lines sat
 * on whatever their line boxes happened to leave — about 3px, a by-product rather than a decision,
 * and one that moved whenever either line's leading changed. Single-line rows have one child here,
 * so the gap costs them nothing.
 */
export const menuItemContentVariants = cva(menuItemContentClass);

/** The baseline-aligned row holding the title and any inline secondary text. */
export const menuItemTitleRowVariants = cva(menuItemTitleRowClass);

/** The row's primary label. Truncates rather than wrapping. */
export const menuItemTitleVariants = cva("truncate");

/** Muted text shown inline after the title (e.g. a translation, a hint). */
export const menuItemSecondaryTextVariants = cva(menuItemSecondaryTextClass);

/**
 * A muted second line beneath the title (the item description).
 *
 * Same fix as `menuItemSecondaryTextClass`, and it matters more here: the description is the only
 * part of a row that gets a line to itself, so borrowed leading showed up as the two lines drifting
 * apart and the row growing for nothing.
 */
export const menuItemDescriptionVariants = cva(menuItemDescriptionClass);

/** A trailing slot for arbitrary content. Sizes an icon child to `--node-size`; adds no tint. */
export const menuItemTrailingVariants = cva(nodeSlotClass);

/**
 * The single-select check shown at a row's inline-end, after the label and before any `trailing`
 * node. Sizes its single child to `--node-size` and tints it with the accent. Decorative — the row
 * carries the selected state.
 */
export const menuItemIndicatorVariants = cva(menuItemIndicatorClass);

/** The leading control slot of a checkbox/radio row, holding the visual toggle. */
export const menuItemControlVariants = cva("flex shrink-0 items-center");

/**
 * Indicator slot inside a radio item: the shared 16px radio ring, always drawn, with the accent dot
 * filling it once the row is selected.
 */
export const menuRadioItemIndicatorVariants = cva(menuRadioItemIndicatorClass);

/**
 * CheckboxItem indicator: the leading checkbox BOX. Composes the shared `checkboxBoxVariants` (the
 * 16px bordered square that fills the accent on `data-checked`) with the node-slot that sizes its
 * inner glyph. Kept mounted by `MenuCheckboxItemIndicator`, so the empty box shows when unchecked;
 * the glyph stays hidden until the box is checked (`data-unchecked:[&>*]:invisible`).
 */
export const menuCheckboxItemIndicatorVariants = cva(menuCheckboxItemIndicatorClass);

/**
 * RadioItem indicator, TICK form (the default). The trailing check that marks the current row of a
 * single-select group — the ring variant above is only for a popup that mixes multi-select and
 * single-select groups.
 */
export const menuRadioItemCheckVariants = cva(menuRadioItemCheckClass);

/** Separator: a thin divider spanning the popup padding. */
export const menuSeparatorVariants = cva(menuSeparatorClass);

/**
 * Label: a non-interactive section heading row that can carry inline-end metadata. Lays out a
 * growing `MenuLabelTitle` and an optional `MenuLabelMeta`.
 *
 * A composite `caption-md` preset (not a bare 12px token) so the heading carries its own `1.2`
 * line-height instead of falling back to the browser's taller default. `medium` rather than
 * `regular`, because `regular` is 450 — the same weight `menuItemDescriptionVariants` now uses at
 * the same size, leading and colour, which left a heading and a caption typographically identical
 * and told apart only by position.
 *
 * `min-h-6` rather than `py-1.5`, and no vertical padding at all: padding around a 12 × 1.2 line
 * box is 6 + 14.4 + 6, so the heading was the one row-shaped thing in a menu whose height could not
 * be a whole number, and every heading pushed the rows under it further off the pixel grid. A FLOOR
 * and not a fixed height, so an inline-end `MenuLabelMeta` taller than 24px still grows the row
 * rather than overflowing into the item below it.
 *
 * Colour stays `text-tertiary`, deliberately. A heading wants to sit below the rows it names, and
 * tertiary is the bottom of the ladder available to it: `text-placeholder` and `text-disabled` are
 * both state tokens here — 7 of 7 placeholder uses sit behind `placeholder:`, and 54 of 54 disabled
 * uses behind `disabled:` / `aria-disabled:` / `aria-busy:` — so applying either unconditionally
 * would be the first such use in the package. `text-disabled` also measures 4.32:1 on light
 * (#71777a on #f9f9f9), under the 4.5:1 floor, and this package's own a11y assertions reject it.
 * Dimming a heading past tertiary needs a content rung propel does not have yet; that is a token
 * decision, not a menu one.
 */
export const menuLabelVariants = cva(
  "flex min-h-6 items-center gap-1.5 px-2 text-caption-md-medium text-tertiary",
);

/** The growing title within a `MenuLabel`. */
export const menuLabelTitleVariants = cva("min-w-0 flex-1 truncate");

/** Trailing metadata pinned at the inline-end of a `MenuLabel`. */
export const menuLabelMetaVariants = cva("shrink-0");

/**
 * Search: the sticky search row pinned above the popup list. No fill: it shows the panel surface
 * through.
 */
export const menuSearchVariants = cva(
  "flex shrink-0 items-center gap-1.5 border-b border-subtle px-3 py-2",
);

/**
 * Search input: the borderless text field in `MenuSearch`.
 *
 * Carries the same type and colour as the rows it filters. `text-secondary` dimmed the query the
 * user had just typed while the results below it sat at `text-primary`, which reads backwards — and
 * the empty state is already handled separately by `placeholder:text-placeholder`, so matching the
 * list costs nothing.
 */
export const menuSearchInputVariants = cva(
  "min-w-0 flex-1 bg-transparent text-body-xs-regular text-primary outline-none placeholder:text-placeholder",
);

/** Footer: a non-interactive footer pinned below the popup list. */
export const menuFooterVariants = cva(menuFooterClass);

export type MenuPopupVariantProps = StrictVariantProps<typeof menuPopupVariants>;

type MenuPopupVariantConfig = VariantProps<typeof menuPopupVariants>;
/**
 * Popup chrome: `raised` is the standalone elevated surface; `flat` is padding-only for use inside
 * an `OverlayPanel`.
 */
export type MenuPopupElevation = NonNullable<MenuPopupVariantConfig["elevation"]>;

type MenuRowVariantConfig = VariantProps<typeof menuRowVariants>;
/**
 * Row look. `neutral` is the standard text hierarchy, `accent` marks the primary action, and
 * `danger` marks a destructive one.
 */
export type MenuItemVariant = NonNullable<MenuRowVariantConfig["variant"]>;
/**
 * How a row arranges its text: `single` for a one-line row, `stacked` when a description sits
 * beneath the title.
 */
export type MenuItemLayout = NonNullable<MenuRowVariantConfig["layout"]>;

export type MenuRowVariantProps = StrictVariantProps<
  typeof menuRowVariants,
  keyof typeof menuRowDefaultVariants
>;

export type MenuCheckboxItemVariantProps = StrictVariantProps<
  typeof menuCheckboxItemVariants,
  keyof typeof menuRowDefaultVariants
>;

export type MenuSubmenuTriggerVariantProps = StrictVariantProps<
  typeof menuSubmenuTriggerVariants,
  keyof typeof menuRowDefaultVariants
>;
