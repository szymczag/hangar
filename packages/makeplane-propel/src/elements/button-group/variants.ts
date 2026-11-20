import { cva, cx, type VariantProps } from "class-variance-authority";

import { type StrictVariantProps } from "../../internal/variant-props";

// ButtonGroup is a connected/segmented container around `ButtonGroupButton`s (Figma "Button
// Group"). The container owns the whole group chrome — the raised white surface, outer border,
// radius, and the dividers between items — so the items themselves stay transparent and
// borderless. Corners of the first/last items are masked by `overflow-hidden`, no child-selector
// overrides needed.
// The outer border is a click-through `::after` overlay painted over the segments rather than a
// layout border: segments keep the full rung height (and the 24px target floor at sm) while the
// group still lands on the same height as a standalone `Button` of that size.
export const buttonGroupVariants = cva(
  cx(
    "relative isolate inline-flex items-center overflow-hidden rounded-md",
    "bg-layer-2 shadow-raised-100",
    "after:pointer-events-none after:absolute after:inset-0 after:z-10 after:rounded-[inherit]",
    "after:border after:border-strong after:content-['']",
    "divide-x divide-strong",
  ),
);

// A ButtonGroupButton is one segment of a ButtonGroup: a transparent, borderless action button
// (Figma's grouped "Buttons" — NOT the standalone secondary `Button`: it has no border/shadow/
// radius of its own, tighter padding, and no `lg` step). The focus ring is inset so it isn't
// clipped by the container's `overflow-hidden`. Each size sets `--node-size` so icon slots
// size their glyph to match.
// A standalone segment defaults to the group scale's denser step (24px); the components tier
// resolves an enclosing ButtonGroup's size first.
const buttonGroupButtonDefaultVariants = {
  size: "sm",
} as const;

export const buttonGroupButtonVariants = cva(
  cx(
    "group inline-flex shrink-0 cursor-pointer items-center justify-center gap-1",
    "bg-layer-transparent whitespace-nowrap text-secondary",
    "transition-colors duration-200 ease-out outline-none",
    "hover:bg-layer-transparent-hover active:bg-layer-transparent-active",
    // Raised above the border overlay so the inset ring isn't painted over at the group's edge.
    "focus-visible:relative focus-visible:z-20 focus-visible:ring-2 focus-visible:ring-accent-strong focus-visible:ring-inset",
    // No `pointer-events-none`: native `disabled` already blocks clicks/`:hover`, and it
    // was making `cursor-not-allowed` a dead class.
    "disabled:cursor-not-allowed disabled:text-disabled",
  ),
  {
    variants: {
      size: {
        // No 20px step, deliberately: segments are contiguous by construction, so the
        // `::before` hit-target expansion the other 20px controls use is unavailable here —
        // adjacent rings would intersect, which voids WCAG 2.5.8's spacing exception. A
        // grouped control's floor is the native 24px target.
        // `px` stays raw deliberately — segments run tighter than the ladder's side padding.
        sm: "h-(--control-height-sm) px-1.5 text-body-xs-medium [--node-size:var(--control-glyph-sm)]",
        // 28px row: the rung's glyph (16px), mirroring `buttonGeometryVariants`.
        md: "h-(--control-height-md) px-2 text-body-xs-medium [--node-size:var(--control-glyph-md)]",
      },
    },
    defaultVariants: buttonGroupButtonDefaultVariants,
  },
);

type ButtonGroupButtonVariantConfig = VariantProps<typeof buttonGroupButtonVariants>;
export type ButtonGroupButtonSize = NonNullable<ButtonGroupButtonVariantConfig["size"]>;

export type ButtonGroupButtonVariantProps = StrictVariantProps<
  typeof buttonGroupButtonVariants,
  keyof typeof buttonGroupButtonDefaultVariants
>;
