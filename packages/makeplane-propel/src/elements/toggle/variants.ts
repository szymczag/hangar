import { cva, cx, type VariantProps } from "class-variance-authority";

import { type StrictVariantProps } from "../../internal/variant-props";

// Toggle family (Figma IconToggle + Toggle-with-text).
//
// Both cvas expose the same three rungs: `xs`/`sm`/`md` — 20/24/28px boxes.
// Pressed/disabled are control state Base UI reflects as `[data-pressed]`/`[data-disabled]`.
//
// size-vocabulary-ok: the labels below are Figma's own magnitude names, which deliberately differ.
// Figma's IconToggle sm/md/lg are those same 20/24/28px boxes, one name up the scale; Figma's text
// Toggle xs/sm/md already match.

/** Shared size rung for `Toggle` and `IconToggle` — both cvas must cover every entry. */
const toggleSizes = ["xs", "sm", "md"] as const;
export type ToggleSize = (typeof toggleSizes)[number];

// ─── IconToggle (square, icon-only) ──────────────────────────────────────────

const iconToggleDefaultVariants = {
  variant: "secondary",
  size: "md",
} as const;

export const iconToggleVariants = cva(
  cx(
    "relative inline-flex shrink-0 cursor-pointer items-center justify-center outline-none",
    "transition-colors",
    "focus-visible:ring-2 focus-visible:ring-accent-strong",
    // Both disabled spellings throughout this file: an `elements` consumer renders a raw
    // `<button disabled>`, while `components` goes through Base UI, which adds `data-disabled`.
    "disabled:cursor-not-allowed data-disabled:cursor-not-allowed",
  ),
  {
    variants: {
      // Figma IconToggle Type: secondary (raised bordered) · ghost (transparent).
      variant: {
        secondary: cx(
          // Figma glyph is placeholder at rest and steps to secondary on hover and when pressed.
          "border border-subtle-1 bg-layer-2 text-icon-placeholder shadow-raised-100",
          "hover:border-strong hover:bg-layer-2-hover hover:text-icon-secondary",
          "active:border-strong active:bg-layer-2-active active:text-icon-secondary",
          // Pressed is gated on not-disabled: `data-pressed:` sorts after `data-disabled:` at equal
          // specificity, so ungated it would repaint a disabled pressed toggle as selected.
          "not-disabled:not-data-disabled:data-pressed:border-strong not-disabled:not-data-disabled:data-pressed:bg-layer-2-selected not-disabled:not-data-disabled:data-pressed:text-icon-secondary",
          // Figma disabled: fill drops to transparent; border stays subtle-1; glyph mutes.
          // Raised shadow is kept (Figma still paints Raised-100 on the disabled secondary).
          "disabled:border-subtle-1 disabled:bg-transparent disabled:text-icon-disabled",
          "data-disabled:border-subtle-1 data-disabled:bg-transparent data-disabled:text-icon-disabled",
        ),
        ghost: cx(
          "bg-layer-transparent text-icon-secondary",
          "hover:bg-layer-transparent-hover",
          "active:bg-layer-transparent-active",
          "not-disabled:not-data-disabled:data-pressed:bg-layer-transparent-selected",
          "disabled:bg-transparent disabled:text-icon-disabled",
          "data-disabled:bg-transparent data-disabled:text-icon-disabled",
        ),
      },
      size: {
        // 20px box / 14px glyph. Transparent `::before` expands the pointer target to 24×24
        // (WCAG 2.5.8) without moving painted pixels — same pattern as IconButton/IconPill xs.
        xs: "size-(--control-height-xs) rounded-(--control-radius-xs) [--node-size:var(--control-glyph-xs)] before:absolute before:-inset-0.5 before:content-['']",
        sm: "size-(--control-height-sm) rounded-(--control-radius-sm) [--node-size:var(--control-glyph-sm)]",
        md: "size-(--control-height-md) rounded-(--control-radius-md) [--node-size:var(--control-glyph-md)]",
      } satisfies Record<ToggleSize, string>,
    },
    defaultVariants: iconToggleDefaultVariants,
  },
);

type IconToggleVariantConfig = VariantProps<typeof iconToggleVariants>;
export type IconToggleVariant = NonNullable<IconToggleVariantConfig["variant"]>;

export type IconToggleVariantProps = StrictVariantProps<
  typeof iconToggleVariants,
  keyof typeof iconToggleDefaultVariants
>;

// ─── Toggle (label + optional start/end icons) ───────────────────────────────

const toggleDefaultVariants = {
  size: "md",
} as const;

// Shared structural base: Figma's bordered layer-2 chip with pressed → selected look.
// No elevation shadow (Figma text Toggle omits Raised-100; IconToggle secondary keeps it).
const toggleSize = {
  // 20px tall, 6px x-pad, 12px caption, 14px nodes; radius-sm (4). Hit-target halo like xs icons.
  xs: cx(
    "h-(--control-height-xs) gap-(--control-gap-xs) rounded-(--control-radius-xs) px-(--control-padding-x-xs)",
    "text-caption-md-regular [--node-size:var(--control-glyph-xs)]",
    "before:absolute before:-inset-0.5 before:content-['']",
  ),
  // 24px tall, 8px x-pad, 13px body-xs, 14px nodes; radius-md (6).
  sm: cx(
    "h-(--control-height-sm) gap-(--control-gap-sm) rounded-(--control-radius-sm) px-(--control-padding-x-sm)",
    "text-body-xs-regular [--node-size:var(--control-glyph-sm)]",
  ),
  // 28px tall, 10px x-pad, 6px gap, 13px body-xs, 14px nodes; radius-md (6).
  md: cx(
    "h-(--control-height-md) gap-(--control-gap-md) rounded-(--control-radius-md) px-(--control-padding-x-md)",
    "text-body-xs-regular [--node-size:var(--control-glyph-md)]",
  ),
} satisfies Record<ToggleSize, string>;

export const toggleVariants = cva(
  cx(
    "relative inline-flex max-w-[120px] shrink-0 cursor-pointer items-center justify-center overflow-clip outline-none",
    // Figma label colour steps with state, identically on every rung: placeholder at rest,
    // secondary on hover, primary when pressed.
    "border border-subtle-1 bg-layer-2 text-placeholder transition-colors",
    "hover:border-strong hover:bg-layer-2-hover hover:text-secondary",
    "active:border-strong active:bg-layer-2-active active:text-secondary",
    // Pressed is gated on not-disabled, as on IconToggle above.
    "not-disabled:not-data-disabled:data-pressed:border-strong not-disabled:not-data-disabled:data-pressed:bg-layer-2-selected not-disabled:not-data-disabled:data-pressed:text-primary",
    "focus-visible:ring-2 focus-visible:ring-accent-strong",
    "disabled:cursor-not-allowed disabled:border-subtle-1 disabled:bg-transparent disabled:text-disabled",
    "data-disabled:cursor-not-allowed data-disabled:border-subtle-1 data-disabled:bg-transparent data-disabled:text-disabled",
  ),
  {
    variants: {
      size: toggleSize,
    },
    defaultVariants: toggleDefaultVariants,
  },
);

export type ToggleVariantProps = StrictVariantProps<
  typeof toggleVariants,
  keyof typeof toggleDefaultVariants
>;

/** The single-line label inside a text Toggle. Truncates past the 120px cap. */
export const toggleLabelVariants = cva("min-w-0 truncate");
