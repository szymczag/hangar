import { cva, cx, type VariantProps } from "class-variance-authority";

import { controlSize } from "../../internal/control-group";
import { fieldControlSurfaceVariants } from "../../internal/field-control-surface";
import { nodeSlotClass } from "../../internal/node-slot";
import { type StrictVariantProps } from "../../internal/variant-props";

/** Root: a horizontal row of character slots (and optional separators). */
export const otpFieldVariants = cva("flex items-center gap-2");

/**
 * Input: a single character cell with the shared field-control surface.
 *
 * Size — controls the box size (lg/xl/2xl); required, no default. The error look isn't a prop: the
 * cell rests at the `subtle-1` border and recolors to `danger` off Base UI's `data-invalid` (set on
 * the digit when the field is wrapped in a `Field.Root invalid`), including the danger focus ring —
 * so there's no hand-rolled danger ring here. Disabled steps the border back to lighter `subtle` so
 * it stays distinct from rest, matching the other field-control surfaces.
 */
export const otpFieldInputVariants = cva(
  cx(
    // Each digit cell is itself the focusable element → `focus: self`.
    fieldControlSurfaceVariants({ focus: "self" }),
    // No base radius here — `size` is required and every branch sets its own
    // `rounded-(--control-radius-*)`; a fixed `rounded-md` here would win the conflicting-utility
    // tie against those and pin every size to 6px (which is exactly the bug this avoids).
    "text-center text-primary outline-none",
    // Per the Figma spec, the OTP cell's own hover/disabled fill differ from the shared surface's
    // (which has no hover at all for a self-focusing control) — added locally, same as Select's
    // trigger, rather than touching the shared primitive every bordered control depends on.
    // `focus:bg-layer-2` is the focused-hover correction `controlGroupClass` carries: nothing else
    // sets a background on `:focus`, and `hover:bg-layer-2-hover` sorts after the base `bg-layer-2`,
    // so without it a focused cell keeps the hover fill for as long as the pointer rests on it —
    // which on an OTP field is the whole time you are typing.
    "hover:border-strong hover:bg-layer-2-hover focus:bg-layer-2",
    "data-disabled:cursor-not-allowed data-disabled:border-subtle data-disabled:bg-surface-1 data-disabled:text-disabled data-disabled:hover:border-subtle data-disabled:hover:bg-surface-1",
  ),
  {
    variants: {
      // Square cells: shared height + a matching width, so `lg`/`xl`/`2xl` are 32/36/40px.
      //
      // size-vocabulary-ok: sm/md/lg below are the pre-#277 names for those same three cells.
      // Those 32/36/40px cells were originally labeled sm/md/lg — the shared scale renamed them
      // rather than resizing them.
      size: {
        // Square cells: the width is the same rung token as the height.
        lg: cx(controlSize.lg, "w-(--control-height-lg) rounded-(--control-radius-lg)"),
        xl: cx(controlSize.xl, "w-(--control-height-xl) rounded-(--control-radius-xl)"),
        "2xl": cx(controlSize["2xl"], "w-(--control-height-2xl) rounded-(--control-radius-2xl)"),
      },
    },
  },
);

type OTPFieldInputVariantConfig = VariantProps<typeof otpFieldInputVariants>;

export type OTPFieldInputSize = NonNullable<OTPFieldInputVariantConfig["size"]>;
export type OTPFieldInputVariantProps = StrictVariantProps<typeof otpFieldInputVariants>;

/**
 * Separator: the divider between groups of slots (e.g. `123-456`). A node-slot: it sizes its single
 * child (an icon, per the Figma spec's minus glyph) to a fixed 16px box, matching the digit cells'
 * height rhythm regardless of `size`.
 */
export const otpFieldSeparatorVariants = cva(
  cx(nodeSlotClass, "size-4 text-tertiary [--node-size:1rem]"),
);

/**
 * Label: the visually-hidden accessible name backing the first slot. Base UI ignores `aria-label`
 * on the first input and names it from `aria-labelledby` instead, so the field needs a real
 * (hidden) label element. Its `sr-only` styling lives here so neither the components tier nor a
 * direct composition carries a raw `className`.
 */
export const otpFieldLabelVariants = cva("sr-only");
