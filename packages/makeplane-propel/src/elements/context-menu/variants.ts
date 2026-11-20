import { cva, cx, type VariantProps } from "class-variance-authority";

import {
  menuCheckboxItemIndicatorClass,
  menuItemContentClass,
  menuItemDescriptionWrapClass,
  menuItemIndicatorClass,
  menuListPopupVariants,
  menuRadioItemCheckClass,
  menuRadioItemIndicatorClass,
  menuRowBaseClass,
  menuRowHighlightClass,
  menuRowPopupOpenHighlightClass,
  menuRowSingleClass,
  menuRowStackedHeightClass,
  menuRowVariantClasses,
  menuSeparatorClass,
  menuSubmenuRowVariantClasses,
} from "../../internal/menu-row-parts";
import { nodeSlotClass } from "../../internal/node-slot";
import { type StrictVariantProps } from "../../internal/variant-props";

/** Popup: shared raised/flat list surface (see `internal/menu-row-parts`). */
export const contextMenuPopupVariants = menuListPopupVariants;

const contextMenuRowDefaultVariants = {
  variant: "neutral",
} as const;

const contextMenuItemDefaultVariants = {
  ...contextMenuRowDefaultVariants,
  layout: "single",
} as const;

// Context menu exposes the shared palette's neutral + danger only (no accent).
const contextMenuRowVariantClasses = {
  neutral: menuRowVariantClasses.neutral,
  danger: menuRowVariantClasses.danger,
} as const;

const contextMenuSubmenuRowVariantClasses = {
  neutral: menuSubmenuRowVariantClasses.neutral,
  danger: menuSubmenuRowVariantClasses.danger,
} as const;

/**
 * Item rows: shared menu-row chrome (`internal/menu-row-parts`) fixed to the single-line pairing. A
 * context menu and a dropdown are the same list opened two ways — row measure comes from the shared
 * base; this family only narrows the look axis to `neutral` | `danger`.
 */
export const contextMenuItemVariants = cva(cx(menuRowBaseClass, menuRowHighlightClass), {
  variants: {
    /**
     * How the row arranges its text. `single` is a one-line, vertically centered row; `stacked`
     * grows to fit a description beneath the label and top-aligns the row's leading content.
     */
    layout: {
      single: menuRowSingleClass,
      stacked: cx(menuRowStackedHeightClass, "cursor-default"),
    },
    /** Row look. `neutral` is the standard text hierarchy and `danger` marks a destructive action. */
    variant: contextMenuRowVariantClasses,
  },
  defaultVariants: contextMenuItemDefaultVariants,
});

/**
 * Submenu trigger row: shared single-line chrome plus popup-open highlight. `group/item` (from the
 * shared base) lets the trailing caret react to the trigger's disabled state.
 */
export const contextMenuSubmenuTriggerVariants = cva(
  cx(menuRowBaseClass, menuRowSingleClass, menuRowHighlightClass, menuRowPopupOpenHighlightClass),
  {
    variants: {
      /** Row look. `neutral` is the standard text hierarchy and `danger` marks a destructive action. */
      variant: contextMenuSubmenuRowVariantClasses,
    },
    defaultVariants: contextMenuRowDefaultVariants,
  },
);

/** The growing label region of an item row; fills the row so trailing regions sit at the inline-end. */
export const contextMenuItemLabelVariants = cva("min-w-0 flex-1 truncate");

/**
 * The text column of a stacked row: grows to fill the row and stacks a `ContextMenuItemLabel` over
 * a `ContextMenuItemDescription`.
 */
export const contextMenuItemContentVariants = cva(menuItemContentClass);

/**
 * A muted line beneath the label — Menu's description chrome, but wrapping rather than truncating:
 * the popup stops growing at its 400px ceiling, so a long description needs the extra lines.
 */
export const contextMenuItemDescriptionVariants = cva(menuItemDescriptionWrapClass);

/** A trailing slot for arbitrary content. Sizes an icon child to `--node-size`; adds no tint. */
export const contextMenuItemTrailingVariants = cva(nodeSlotClass);

/**
 * Trailing single-select check gutter — shared `menuItemIndicatorClass` (Figma: icon, then label,
 * then check).
 */
export const contextMenuItemIndicatorVariants = cva(menuItemIndicatorClass);

/**
 * The tick region of a checkbox row. Kept mounted for a stable gutter; Base UI marks it
 * `data-unchecked` while off, which hides the glyph (its own contract — the shared item-indicator
 * recipe keys off `data-selected`, which checkbox/radio indicators never receive).
 */
export const contextMenuCheckboxItemIndicatorVariants = cva(menuCheckboxItemIndicatorClass);

/**
 * RadioItem indicator, TICK form (the default) — the trailing check marking the current row of a
 * single-select group. The ring variant is reserved for a popup that mixes multi-select and
 * single-select groups.
 */
export const contextMenuRadioItemCheckVariants = cva(menuRadioItemCheckClass);

/** The ring region of a radio row — shared with Menu's radio indicator. */
export const contextMenuRadioItemIndicatorVariants = cva(menuRadioItemIndicatorClass);

/** Separator: a thin divider spanning the popup padding. */
export const contextMenuSeparatorVariants = cva(menuSeparatorClass);

export type ContextMenuPopupVariantProps = StrictVariantProps<typeof contextMenuPopupVariants>;

type ContextMenuPopupVariantConfig = VariantProps<typeof contextMenuPopupVariants>;
/**
 * Popup chrome: `raised` is the standalone elevated surface; `flat` is padding-only for use inside
 * an `OverlayPanel`.
 */
export type ContextMenuPopupElevation = NonNullable<ContextMenuPopupVariantConfig["elevation"]>;

type ContextMenuItemVariantConfig = VariantProps<typeof contextMenuItemVariants>;
/** Row look. `neutral` is the standard text hierarchy and `danger` marks a destructive action. */
export type ContextMenuItemVariant = NonNullable<ContextMenuItemVariantConfig["variant"]>;

/**
 * How a row arranges its text: `single` for a one-line row, `stacked` when a description sits
 * beneath the label.
 */
export type ContextMenuItemLayout = NonNullable<ContextMenuItemVariantConfig["layout"]>;

export type ContextMenuItemVariantProps = StrictVariantProps<
  typeof contextMenuItemVariants,
  keyof typeof contextMenuItemDefaultVariants
>;

type ContextMenuSubmenuTriggerVariantConfig = VariantProps<
  typeof contextMenuSubmenuTriggerVariants
>;
/** Row look. `neutral` is the standard text hierarchy and `danger` marks a destructive action. */
export type ContextMenuSubmenuTriggerVariant = NonNullable<
  ContextMenuSubmenuTriggerVariantConfig["variant"]
>;

export type ContextMenuSubmenuTriggerVariantProps = StrictVariantProps<
  typeof contextMenuSubmenuTriggerVariants,
  keyof typeof contextMenuRowDefaultVariants
>;
