import { cva, cx } from "class-variance-authority";

import { checkboxBoxVariants } from "./checkbox-box";
import { itemIndicatorClass, itemIndicatorUncheckedClass } from "./item-indicator";
import { nodeSlotClass } from "./node-slot";
import { popupSurfaceClass } from "./popup-surface";
import { radioCircleVariants } from "./radio-circle";

/**
 * Shared menu-list furniture used by both the dropdown `Menu` and `ContextMenu` families (rule 4a).
 * Chrome that must stay byte-identical across the two lives here — the elevated list popup, the
 * interactive row base, the row look palette, the trailing single-select check gutter, the radio
 * ring indicator, and the separator — so a Figma tweak lands once. Family-only pieces (Menu's
 * stacked layout / accent / search / footer; ContextMenu's thinner variant set) stay in each
 * family's `variants.ts` and compose these.
 */

/**
 * Raised/flat list popup, shared by `Menu` and `ContextMenu`'s own `popupVariants`.
 *
 * `flat` carries its own fade tied to `data-ending-style`: Base UI measures the transition duration
 * on this exact element (the one it renders via `render`) to decide how long to keep the popup
 * mounted while closing, not on the surrounding `OverlayPanel` card — an ancestor's transition
 * doesn't count. `OverlayPanel` reacts to the nested popup's `data-ending-style` via
 * `has-[[role=menu][data-ending-style]]` (and the Popover `role=dialog` equivalent) so the whole
 * card scales and fades out in step, without treating a Combobox item indicator's own ending-style
 * as the panel closing.
 */
export const menuListPopupVariants = cva("", {
  variants: {
    /**
     * Whether the popup draws its own surface. `raised` is the standalone surface — its own
     * elevation, radius, border and animated transform origin, used when the popup IS the family's
     * outer chrome (the elements-tier story), floored at the shared popup width floor like every
     * other standalone menu. `flat` is the padded list that sits _inside_ an `OverlayPanel` — the
     * family's ready-made content (`MenuContent`, `ContextMenuContent`) provides the elevated,
     * scrollable shell, so the popup only contributes padding.
     */
    elevation: {
      raised: cx(popupSurfaceClass, "min-w-(--popup-width-min) p-1"),
      flat: "p-1 transition-opacity duration-150 outline-none data-ending-style:opacity-0",
    },
  },
});

/**
 * Interactive row chrome shared by every menu-style item / link / checkbox / radio / submenu
 * trigger: full-width flex row, control-scale type, icon `--node-size`, disabled treatment.
 * `group/item` lets trailing carets react to the row's disabled state.
 */
export const menuRowBaseClass = cx(
  "group/item flex w-full gap-(--control-gap-md) rounded-md px-2 text-body-xs-regular outline-none select-none [--node-size:var(--control-glyph-md)]",
  "data-disabled:pointer-events-none data-disabled:text-disabled",
);

/** Pointer/keyboard highlight fill — background only, leaves the row's text colour alone. */
export const menuRowHighlightClass = "data-highlighted:bg-layer-transparent-hover";

/** Keep the highlight while a submenu stays open beside the trigger. */
export const menuRowPopupOpenHighlightClass = "data-popup-open:bg-layer-transparent-hover";

/**
 * Single-line 32px row height (`h-8`, the ladder's `lg` step — the same fixed row `ListItem` and
 * the Select/Autocomplete listbox compositions use, so every dropdown row in the library lands on
 * one height). No cursor styling of its own — `MenuItem`'s standalone `layout.single` composes this
 * bare, so the height ramp has one source of truth without picking up `menuRowSingleClass`'s
 * `cursor-default` (a MenuItem row has never had it; that split is deliberate, not an oversight of
 * this extraction).
 *
 * Only the box grows: the row's type, gap and glyph stay on the `md` rung (`menuRowBaseClass`), the
 * way `ListItem` pairs its 32px box with its own type scale.
 */
export const menuRowSingleHeightClass = "h-8 items-center";

/** Single-line 32px row, with the `cursor-default` every row but plain `MenuItem` carries. */
export const menuRowSingleClass = cx(menuRowSingleHeightClass, "cursor-default");

/**
 * Two-line row that grows to fit a description beneath the title and top-aligns its leading and
 * trailing content with the title line, not the row's vertical centre. Floored at the same 32px as
 * the single-line row, so a stacked row with no description still matches its neighbours. The
 * leading icon — whatever sits right before the `menu-item-content` column — drops `mt-0.5` so it
 * centres on the title line rather than riding the row's top edge.
 */
export const menuRowStackedHeightClass = cx(
  "min-h-8 items-start py-1.5",
  "[&>:has(+[data-slot=menu-item-content])]:mt-0.5",
);

/**
 * The text column of a row: grows to fill it (so trailing nodes sit at the inline-end) and stacks
 * the title over an optional description, `gap-1` apart.
 */
export const menuItemContentClass = "flex min-w-0 flex-1 flex-col gap-1";

/** The baseline-aligned row holding a row's title and any inline secondary text. */
export const menuItemTitleRowClass = "flex min-w-0 items-baseline gap-1.5";

/**
 * Muted text shown inline after a row's title (e.g. a translation, a hint).
 *
 * `text-caption-md-regular` rather than a bare 12px token: same size, but the preset carries its
 * own `1.2` line-height. A bare size token has no companion leading, so this text inherited the
 * row's — since #246 that is `text-body-xs-regular`'s `1.54`, a line box built for 13px type.
 */
export const menuItemSecondaryTextClass =
  "shrink-0 truncate text-caption-md-regular text-tertiary group-data-disabled/item:text-disabled";

/**
 * A muted line beneath the title. `text-caption-md-regular` rather than a bare 12px token so it
 * carries its own `1.2` leading instead of inheriting the row's 13px line box. Overflow is left to
 * each family: `Menu` truncates to one line, `ContextMenu` wraps once the popup hits its width
 * ceiling.
 */
const menuItemDescriptionBaseClass =
  "text-caption-md-regular text-tertiary group-data-disabled/item:text-disabled";

/** One-line description that truncates past the row width. */
export const menuItemDescriptionClass = cx(menuItemDescriptionBaseClass, "truncate");

/** Description that wraps onto as many lines as it needs, breaking an overlong word if it must. */
export const menuItemDescriptionWrapClass = cx(menuItemDescriptionBaseClass, "wrap-break-word");

/**
 * Row look palette. `neutral` is the standard hierarchy, `accent` marks the primary action,
 * `danger` marks a destructive one. Highlight locks keep accent/danger text from flipping when the
 * fill changes.
 */
export const menuRowVariantClasses = {
  neutral: "text-primary",
  accent: "text-accent-primary data-disabled:text-disabled data-highlighted:text-accent-primary",
  danger: "text-danger-primary data-disabled:text-disabled data-highlighted:text-danger-primary",
} as const;

/**
 * Submenu-trigger look palette — same as `menuRowVariantClasses`, plus `data-popup-open` text locks
 * so accent/danger stay put while the nested menu is open.
 */
export const menuSubmenuRowVariantClasses = {
  neutral: "text-primary",
  accent:
    "text-accent-primary data-disabled:text-disabled data-highlighted:text-accent-primary data-popup-open:text-accent-primary",
  danger:
    "text-danger-primary data-disabled:text-disabled data-highlighted:text-danger-primary data-popup-open:text-danger-primary",
} as const;

/**
 * Trailing single-select check gutter — composed at the row's inline-END, after the label and
 * before any `trailing` node. A multi-select checkbox keeps the LEADING control slot instead
 * (`menuItemControlVariants`), so the two markers never share a column. `h-5 w-4` reserves the
 * column on unselected rows too, so toggling a selection never re-truncates a label;
 * `not-data-selected:invisible` hides the glyph without collapsing it.
 */
export const menuItemIndicatorClass = cx(itemIndicatorClass, "h-5 w-4");

/**
 * Radio-row selection control: the same 16px ring the standalone `Radio` draws
 * (`internal/radio-circle`), with the row's glyph child as its inner dot. Base UI stamps
 * `data-checked` / `data-unchecked` / `data-disabled` on the indicator itself, which is what lets
 * one class serve both hosts.
 *
 * The RING is always drawn — only the dot hides while unchecked. An earlier version hid the whole
 * indicator on `data-unchecked`, which left unselected rows with an empty 16px hole and made a
 * radio group read as a list of plain rows with one stray dot. Showing the empty ring is the same
 * contract the checkbox row has always had with its empty box, and it is what makes the group
 * legible as a set of mutually exclusive options rather than a single decoration.
 */
export const menuRadioItemIndicatorClass = cx(
  radioCircleVariants(),
  // The dot itself is `internal/radio-dot` — the same styled element the standalone `Radio`
  // renders — so this class owns only the hide rule. The dot was a lucide `Circle` scaled to
  // `size-2` (a 6.67px stroked-and-filled circle in an 8px box), visibly softer and smaller than
  // the standalone control's span; grafting the shared element removes the second geometry.
  "data-unchecked:[&>*]:invisible",
);

/**
 * CheckboxItem indicator: the leading checkbox BOX — the shared `checkboxBoxVariants` square with
 * the node-slot that sizes its inner glyph. Kept mounted by the host, so the EMPTY box shows while
 * unchecked and only the glyph hides.
 *
 * Shared, not per-family (rule 4a): the context menu drew a bare accent tick that rendered nothing
 * at all when unchecked, so an unchecked row read as absent rather than off — the same defect the
 * radio ring had. One class now, both families.
 */
export const menuCheckboxItemIndicatorClass = cx(
  checkboxBoxVariants(),
  nodeSlotClass,
  "data-unchecked:[&>*]:invisible",
);

/**
 * Radio-row selection control, TICK form — the default. A single-select group inside a menu marks
 * the current row with the same trailing check every other single-select row uses; the ring
 * (`menuRadioItemIndicatorClass`) is reserved for the one case that needs it, a popup that mixes a
 * multi-select group with a single-select one, where the two need telling apart.
 */
export const menuRadioItemCheckClass = cx(itemIndicatorUncheckedClass, "h-5 w-4");

/** A non-interactive footer pinned below a popup list (a hint, a count). */
export const menuFooterClass =
  "shrink-0 border-t border-subtle bg-layer-2 px-3 py-2 text-caption-md-regular text-tertiary";

/** Separator spanning the popup's horizontal padding. */
export const menuSeparatorClass = "-mx-1 my-1 border-t border-subtle";
