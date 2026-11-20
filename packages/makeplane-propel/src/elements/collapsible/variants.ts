import { cva, cx, type VariantProps } from "class-variance-authority";

import { disclosureTriggerClass } from "../../internal/disclosure-trigger";
import type { StrictVariantProps } from "../../internal/variant-props";

// Inline disclosures retain their default chrome; sidebar placement aligns an independent
// action before the indicator and removes body insets for navigation rows.

export const collapsibleVariants = cva(
  // Full width so centered hosts (docs `ComponentExample`) don't shrink-wrap to the
  // title cluster when closed and jump when the panel opens wider.
  "w-full",
);

const collapsibleHeaderDefaultVariants = { placement: "inline" } as const;
export const collapsibleHeaderVariants = cva("w-full", {
  variants: {
    placement: {
      inline: "flex",
      sidebar:
        "grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-x-1 rounded-lg px-2 hover:bg-layer-transparent-hover has-[>[data-disabled]]:hover:bg-transparent",
    },
  },
  defaultVariants: collapsibleHeaderDefaultVariants,
});

// Leading icons inherit the trigger glyph size. Sidebar disclosure indicators use the
// compact glyph token while inline disclosures retain the inherited size.
const collapsibleTriggerDefaultVariants = { placement: "inline" } as const;
export const collapsibleTriggerVariants = cva(
  cx(
    disclosureTriggerClass,
    // `flex-1 min-w-0` fills `CollapsibleHeader` so leftover space stays the toggle hit target
    // while a trailing action sits at the inline-end. Without a header parent, `display: flex`
    // already blockifies the button so it still spans the root.
    "min-w-0 flex-1 bg-layer-transparent [--node-size:var(--control-glyph-lg)]",
  ),
  {
    variants: {
      placement: {
        inline: "px-3 py-2",
        sidebar:
          "col-span-3 col-start-1 row-start-1 grid h-8 grid-cols-subgrid gap-x-1 px-0 py-0 [&>[data-slot=disclosure-indicator]]:col-start-3 [&>[data-slot=disclosure-indicator]]:[--node-size:var(--control-glyph-sm)]",
      },
    },
    defaultVariants: collapsibleTriggerDefaultVariants,
  },
);

const collapsibleTriggerTrailingDefaultVariants = { placement: "inline" } as const;
export const collapsibleTriggerTrailingVariants = cva("flex shrink-0 items-center gap-2", {
  variants: {
    placement: {
      inline: "pe-3",
      sidebar: "relative col-start-2 row-start-1",
    },
  },
  defaultVariants: collapsibleTriggerTrailingDefaultVariants,
});

// The inline trigger's label. Unlike accordion (title grows so the caret sits at the
// inline-end), Figma packs `[icon?][title][chevron]` as a content cluster —
// no `flex-1`. Figma's sample title is `whitespace-nowrap` + `shrink-0` (short
// demo copy); we keep `min-w-0` and allow wrap so long labels don't overflow —
// same usability choice as Accordion's `disclosureTriggerTitleClass`.
const collapsibleTriggerTitleDefaultVariants = { placement: "inline" } as const;
export const collapsibleTriggerTitleVariants = cva("min-w-0 text-start", {
  variants: {
    placement: {
      inline: "",
      sidebar:
        "col-start-1 flex min-w-0 items-center gap-2 overflow-hidden text-body-xs-semibold text-tertiary [&>*]:truncate",
    },
  },
  defaultVariants: collapsibleTriggerTitleDefaultVariants,
});

export const collapsiblePanelVariants = cva(
  cx(
    // Base UI exposes the panel's natural size as `--collapsible-panel-height`;
    // transition from it to 0 on the starting/ending styles for a smooth collapse.
    // Geometry/animation only — Figma body type lives on `CollapsiblePanelContent` so
    // consumers like `ListSection` (children directly in the panel) do not inherit
    // Collapsible prose tokens.
    "h-(--collapsible-panel-height) overflow-hidden",
    "transition-[height] duration-200 ease-out",
    "data-ending-style:h-0 data-starting-style:h-0",
  ),
);

// Padded inner content + Figma body prose. Padding and type live here, never on the
// height-animating `CollapsiblePanel` (padding there would offset measured height;
// type on the panel would leak into List section bodies). `sidebar` placement keeps its own
// `p-0` default; `hug` is an independent override so `inline` (or a future placement) can also
// drop its padding without switching placement. Expressed via a compound variant, never
// concatenating `px-3 pb-3` alongside `p-0` in the same class string.
const collapsiblePanelContentDefaultVariants = { placement: "inline", hug: false } as const;
export const collapsiblePanelContentVariants = cva("text-body-xs-regular text-secondary", {
  variants: {
    placement: {
      inline: "",
      sidebar: "p-0",
    },
    hug: {
      true: "p-0",
      false: "",
    },
  },
  compoundVariants: [{ placement: "inline", hug: false, class: "px-3 pb-3" }],
  defaultVariants: collapsiblePanelContentDefaultVariants,
});

export type CollapsibleHeaderPlacement = NonNullable<
  VariantProps<typeof collapsibleHeaderVariants>["placement"]
>;
export type CollapsibleHeaderVariantProps = StrictVariantProps<
  typeof collapsibleHeaderVariants,
  keyof typeof collapsibleHeaderDefaultVariants
>;

export type CollapsibleTriggerPlacement = NonNullable<
  VariantProps<typeof collapsibleTriggerVariants>["placement"]
>;
export type CollapsibleTriggerVariantProps = StrictVariantProps<
  typeof collapsibleTriggerVariants,
  keyof typeof collapsibleTriggerDefaultVariants
>;

export type CollapsibleTriggerTrailingPlacement = NonNullable<
  VariantProps<typeof collapsibleTriggerTrailingVariants>["placement"]
>;
export type CollapsibleTriggerTrailingVariantProps = StrictVariantProps<
  typeof collapsibleTriggerTrailingVariants,
  keyof typeof collapsibleTriggerTrailingDefaultVariants
>;

export type CollapsibleTriggerTitlePlacement = NonNullable<
  VariantProps<typeof collapsibleTriggerTitleVariants>["placement"]
>;
export type CollapsibleTriggerTitleVariantProps = StrictVariantProps<
  typeof collapsibleTriggerTitleVariants,
  keyof typeof collapsibleTriggerTitleDefaultVariants
>;

export type CollapsiblePanelContentPlacement = NonNullable<
  VariantProps<typeof collapsiblePanelContentVariants>["placement"]
>;
export type CollapsiblePanelContentVariantProps = StrictVariantProps<
  typeof collapsiblePanelContentVariants,
  keyof typeof collapsiblePanelContentDefaultVariants
>;
