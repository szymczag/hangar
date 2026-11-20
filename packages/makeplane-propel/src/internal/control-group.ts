import { cx } from "class-variance-authority";

import { fieldControlSurfaceVariants } from "./field-control-surface";

/**
 * The shared interaction chrome for a bordered group that WRAPS a separately-focusable form control
 * — the input, textarea, autocomplete, combobox (input row and chips frame), and number-field
 * frames. Composes the `focus: "within"` control surface and adds the one interaction design every
 * input box shares (before this, input/text-area carried it and the pickers had silently drifted to
 * a static frame):
 *
 * - A color/border/shadow transition,
 * - The rest hover (`border-strong` + `layer-2-hover` fill),
 * - The focused-hover correction (keep the accent border and flat fill while typing),
 * - The disabled guard in BOTH selector forms — `:has(:disabled)` for a frame around a native control
 *   and `data-disabled` for a Base UI group that mirrors state as an attribute. A disabled frame
 *   keeps its resting `subtle-1` border and `layer-2` fill, as in Figma; only the ring and hover
 *   go.
 *
 * Families add only their own geometry: width, alignment, gap, radius, padding/size.
 */
export const controlGroupClass = cx(
  fieldControlSurfaceVariants({ focus: "within" }),
  "group/control flex transition-[color,background-color,border-color,box-shadow]",
  "hover:border-strong hover:bg-layer-2-hover",
  "focus-within:bg-layer-2 focus-within:hover:border-accent-strong focus-within:hover:bg-layer-2",
  "has-[:disabled]:cursor-not-allowed has-[:disabled]:border-subtle-1 has-[:disabled]:bg-layer-2 has-[:disabled]:ring-0 has-[:disabled]:hover:border-subtle-1",
  "data-disabled:cursor-not-allowed data-disabled:border-subtle-1 data-disabled:bg-layer-2 data-disabled:text-disabled data-disabled:ring-0 data-disabled:hover:border-subtle-1",
);

/**
 * THE single-line control size scale — one meaning per step across every bordered form control
 * (input, autocomplete, combobox, select trigger, otp digit). A step always means: height, text
 * size, and glyph `--node-size`.
 *
 * `md` 28px / body-xs / 16px glyphs · `lg` 32px / body-sm / 16px · `xl` 36px / body-sm / 16px ·
 * `2xl` 40px / body-md / 20px. Families expose the steps their Figma spec defines and add only
 * their own geometry (padding, width, radius). Two families sit outside it by design: `text-area`
 * runs its own typography-only scale one step below (a wrapped paragraph reads smaller than a
 * single-line value at the same nominal size), and `number-field` runs `sm`–`lg` with steppers one
 * rung below the frame (`numberFieldStepperSize`) inside a 2px outer inset (1px `border-sm` + 1px
 * `p-px`; no `xs` — halo rung).
 */
// size-vocabulary-ok: the labels below are each family's PRE-unification names, kept as the record
// of what this scale replaced. They are not claims about any current axis.
//
// Before this, every family kept its own scale and they disagreed: input was padding-based
// `md/lg/xl`, autocomplete/select ran `sm/md/lg` at 28/32/36px but differed on the text size of the
// SAME step, the otp digits ran the same pixel scale one label off (32/36/40 as "sm/md/lg"), and
// combobox had no axis at all.
export const controlSize = {
  md: "min-h-(--control-height-md) text-body-xs-regular [--node-size:var(--control-glyph-md)]",
  lg: "min-h-(--control-height-lg) text-body-sm-regular [--node-size:var(--control-glyph-lg)]",
  xl: "min-h-(--control-height-xl) text-body-sm-regular [--node-size:var(--control-glyph-xl)]",
  "2xl": "min-h-(--control-height-2xl) text-body-md-regular [--node-size:var(--control-glyph-2xl)]",
} as const;

// There is deliberately no shared `controlLabelClass` here anymore: `SelectLabel` steps with the
// trigger's own size axis (its label has a real size to thread), and `SliderLabel` — whose `size`
// is thumb geometry, not type — keeps the fixed 13px treatment in its own cva. One consumer is
// not a shared class (rule 4a's rule of 3).
