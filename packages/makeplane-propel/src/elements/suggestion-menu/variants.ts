import { cva, cx } from "class-variance-authority";

import { nodeSlotClass } from "../../internal/node-slot";
import { popupWidthRule } from "../../internal/popup-width";
import { type StrictVariantProps } from "../../internal/variant-props";

const suggestionMenuDefaultVariants = { width: "fixed" } as const;

/**
 * The popup surface, scrolling past 320px of rows. `width="fixed"` is a 320px column (the Figma
 * `/command dropdown` frame). `width="fit"` is the popup family's width rule
 * (`internal/popup-width`): the widest row, between 204px and 400px, where long labels truncate;
 * the components tier holds that width while the menu is open. `fixed` never overflows its
 * container; `fit` yields only to the viewport, so in a container narrower than 204px it overflows.
 * The shadow is Figma's `shadow-xl` pair, not a propel elevation token: design chose it for this
 * surface over `shadow-overlay-100`, and no other popup uses it yet.
 */
export const suggestionMenuVariants = cva(
  cx(
    "max-h-80 overflow-y-auto overscroll-contain rounded-lg border-sm border-subtle-1 bg-layer-2",
    "shadow-[0px_10px_10px_-5px_rgb(41_47_61/0.04),0px_20px_25px_-5px_rgb(41_47_61/0.1)]",
  ),
  {
    variants: {
      width: {
        fixed: "w-80 max-w-full",
        // The room is the viewport, set on the menu itself so an ancestor positioner's
        // `--available-width` (it measures that positioner's anchor, not this menu) cannot leak in.
        // Not `100%`: hosts float the menu in a shrink-to-fit box (`position: fixed`), where `100%`
        // is the rows' own width and the floor and hold collapse to it.
        fit: cx("w-max [--available-width:100vw]", popupWidthRule),
      },
    },
    defaultVariants: suggestionMenuDefaultVariants,
  },
);

export type SuggestionMenuVariantProps = StrictVariantProps<
  typeof suggestionMenuVariants,
  keyof typeof suggestionMenuDefaultVariants
>;

/** A section: 4px of padding around its rows, divided from the next section by a hairline. */
export const suggestionMenuGroupVariants = cva("border-b-sm border-subtle p-1 last:border-b-0");

/** A section heading: a 26px caption row, inset to line up with the row labels below it. */
export const suggestionMenuLabelVariants = cva(
  "truncate px-2 py-1.5 text-caption-md-regular text-tertiary",
);

/**
 * A suggestion row: 34px (6px padding around a 14px line, floored at 34 because the 154% line box
 * is 21.56px, not the 22 Figma rounds to), a 16px glyph, and the highlight fill on
 * `data-highlighted`. The highlight is set by whoever owns the keyboard, not by focus — the row is
 * never focused — so there is no `focus-visible` style to add.
 */
export const suggestionMenuItemVariants = cva(
  cx(
    "flex min-h-8.5 w-full cursor-pointer items-center gap-1.5 rounded-md px-2 py-1.5 outline-none select-none",
    "text-body-sm-regular text-primary [--node-size:var(--control-glyph-lg)]",
    "data-highlighted:bg-layer-transparent-hover",
  ),
);

/** The leading glyph slot, tinted `icon-secondary`. */
export const suggestionMenuItemIconVariants = cva(cx(nodeSlotClass, "text-icon-secondary"));

/** The row label. Fills the row, so trailing content sits at the inline-end, and truncates. */
export const suggestionMenuItemTitleVariants = cva("min-w-0 flex-1 truncate");

/** The inline-end slot (a badge, a shortcut). Sizes an icon child; adds no tint. */
export const suggestionMenuItemTrailingVariants = cva(nodeSlotClass);
