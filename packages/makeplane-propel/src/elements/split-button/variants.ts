import { cva, cx, type VariantProps } from "class-variance-authority";

import { type StrictVariantProps } from "../../internal/variant-props";

// SplitButton is the two-segment frame around a main action button and a menu-opening icon button
// (Figma "Split button"). Figma ships only neutral primary/secondary — no danger split button. The
// segments keep their own control chrome; the frame only owns how they sit together — and that
// layout differs by variant:
//
//   - **primary** — two discrete pills 1px apart (`gap-px`). Outer corners keep each segment's
//     `rounded-md`; the facing (split) edges are flattened via longhand `rounded-e/s-none`
//     (out-cascades the segment shorthand). No divider — canvas shows in the gap.
//     Figma flattens them outright: every segment of both split-button sets measures
//     `[6,0,0,6]` leading and `[0,6,6,0]` trailing (Icon Split button 9441:1252, Split button
//     3648:2824). An earlier 2px soft-square here had no basis in the design.
//   - **secondary** — one connected outline frame. Inner-edge radius flattening via child
//     selectors (longhand `rounded-s/e-none` intentionally out-cascades a segment's own
//     shorthand `rounded-md`), and the doubled border at the junction collapses to one
//     (`border-s-0` on trailing children; the leading segment's `border-e` IS the divider).
//
// A focused segment is lifted (`z-10` under `isolate`) so its offset focus ring paints over the
// adjacent segment instead of underneath it.
//
// Child selectors key off `:first-child`/`* + *` and NEVER `:last-child`: while the menu is open,
// Base UI appends focus-guard `<span>`s after the trigger inside the frame, so the trigger is not
// reliably the last child (keying the flattening off `:not(:last-child)` visibly ate the open
// trigger's end radius).
//
// `variant` is declared for the split-button Types only — primary and secondary; there is no
// tertiary/ghost split button. `size` is color-less: it constrains the composed frame to the
// segments' shared size step (both segments of a split button are always the same size).
export const splitButtonVariants = cva(
  cx("isolate inline-flex items-stretch", "[&>*:focus-visible]:z-10"),
  {
    variants: {
      variant: {
        primary: cx("gap-px", "[&>*:first-child]:rounded-e-none", "[&>*+*]:rounded-s-none"),
        secondary: cx(
          "[&>*+*]:rounded-s-none [&>*:first-child]:rounded-e-none",
          "[&>*+*]:border-s-0 [&>*:first-child]:border-e",
          "[&:has(:disabled)>*:first-child]:border-e-subtle",
        ),
      },
      // No `xs`: the segments sit 1px apart (`primary`) or flush (`secondary`), so the 20px
      // rung's transparent `::before` hit ring would overlap the neighboring segment and void
      // WCAG 2.5.8's spacing exception — the same reason ButtonGroupButton has no 20px step.
      // A grouped control's floor is the native 24px target.
      size: { sm: "", md: "", lg: "" },
    },
  },
);

type SplitButtonVariantConfig = VariantProps<typeof splitButtonVariants>;
export type SplitButtonVariant = NonNullable<SplitButtonVariantConfig["variant"]>;
export type SplitButtonSize = NonNullable<SplitButtonVariantConfig["size"]>;

// No `defaultVariants` today, so every axis is required.
export type SplitButtonVariantProps = StrictVariantProps<typeof splitButtonVariants>;
