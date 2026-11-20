import { cx } from "class-variance-authority";

import { checkboxBoxVariants } from "./checkbox-box";
import { nodeSlotClass } from "./node-slot";

/**
 * The shared selected-check slot chrome (rule 4a): an `icon-secondary` node slot that hides its
 * glyph while the row is unselected (`data-selected` comes from the Base UI `ItemIndicator` graft,
 * which passes `keepMounted` so the gutter column holds). Side-agnostic on its own; every family
 * composes it at the row's inline-END, the single-select half of the Figma split that keeps the
 * multi-select checkbox leading. Composed by the select/combobox/menu/context-menu item indicators
 * — before this each re-spelled it, and combobox had drifted to an untinted check.
 */
const itemIndicatorBaseClass = cx(nodeSlotClass, "text-icon-secondary [--node-size:1rem]");

export const itemIndicatorClass = cx(itemIndicatorBaseClass, "not-data-selected:invisible");

/**
 * The same slot keyed off `data-unchecked` instead of `data-selected` — for a Base UI
 * `RadioItemIndicator`, which stamps `data-checked` / `data-unchecked` on itself rather than the
 * `data-selected` an `ItemIndicator` graft carries. Same chrome, different state attribute; the
 * geometry stays in `itemIndicatorBaseClass` so the two never drift.
 */
export const itemIndicatorUncheckedClass = cx(itemIndicatorBaseClass, "data-unchecked:invisible");

/**
 * Multi-select checkbox-row indicator: the LEADING checkbox box, the marker that stays at the
 * inline-start while the single-select check sits at the inline-end. Keyed off `data-selected` —
 * what Base UI's Select and Combobox `ItemIndicator` stamp, not the `data-checked` a Menu checkbox
 * item carries — so the filled look and glyph visibility follow the option's selection. Kept
 * mounted so the empty box shows when unselected. `data-indeterminate` (set by `ComboboxSelectAll`
 * when only some items are selected) gets the same fill; the glyph (`Check` vs `Minus`) is chosen
 * in JS by the consumer. Shared by the select and combobox families (rule 4a).
 */
export const checkboxItemIndicatorClass = cx(
  checkboxBoxVariants(),
  nodeSlotClass,
  "data-selected:bg-accent-primary data-selected:text-icon-on-color data-selected:shadow-none",
  "data-selected:not-data-disabled:hover:bg-accent-primary-hover",
  "data-indeterminate:bg-accent-primary data-indeterminate:text-icon-on-color data-indeterminate:shadow-none",
  "data-indeterminate:not-data-disabled:hover:bg-accent-primary-hover",
  "not-data-selected:not-data-indeterminate:[&>*]:invisible",
);
