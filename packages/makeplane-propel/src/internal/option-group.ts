import { cva } from "class-variance-authority";

export const optionGroupDensityClasses = {
  comfortable: "gap-2",
  compact: "gap-0",
} as const;

/**
 * A stacked group of labeled option rows (rule 4a) — the checkbox group and radio group share the
 * column layout and the `density` axis verbatim, so both families alias this cva. `min-w-0` lets a
 * long option label shrink instead of overflowing a constrained flex/grid parent.
 */
export const optionGroupVariants = cva("flex min-w-0 flex-col", {
  variants: {
    density: optionGroupDensityClasses,
  },
});
