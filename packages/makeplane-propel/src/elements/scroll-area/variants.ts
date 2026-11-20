import { cva, type VariantProps } from "class-variance-authority";

import { type StrictVariantProps } from "../../internal/variant-props";

const scrollAreaDefaultVariants = {
  variant: "overlay",
  size: "md",
  orientation: "vertical",
} as const;

// The inset lane is padding on the ROOT, not the viewport: padding on a scroll container scrolls
// with its content, so with `both` a viewport lane would only appear at the far scroll edge. The
// root is the rails' containing block (they pin to its padding box), so root padding narrows the
// viewport itself and the rails sit in a lane that never moves.
export const scrollAreaVariants = cva("relative flex h-full min-h-0 w-full flex-1 flex-col", {
  variants: {
    /**
     * `overlay` — the scrollbar floats over the content. `inset` — the root always reserves the
     * track on each rendered axis (like `scrollbar-gutter: stable`), so the thumb never covers
     * content and content never reflows when it starts or stops overflowing.
     */
    variant: { overlay: "", inset: "" },
    /** Track the inset lane matches; mirrors the scrollbar `size`. */
    size: { sm: "", md: "", lg: "" },
    /** Which axes render a scrollbar, and so which edges an inset lane reserves. */
    orientation: { vertical: "", horizontal: "", both: "" },
  },
  compoundVariants: [
    {
      variant: "inset",
      orientation: ["vertical", "both"],
      size: "sm",
      class: "pe-(--scrollbar-track-sm)",
    },
    {
      variant: "inset",
      orientation: ["vertical", "both"],
      size: "md",
      class: "pe-(--scrollbar-track-md)",
    },
    {
      variant: "inset",
      orientation: ["vertical", "both"],
      size: "lg",
      class: "pe-(--scrollbar-track-lg)",
    },
    {
      variant: "inset",
      orientation: ["horizontal", "both"],
      size: "sm",
      class: "pb-(--scrollbar-track-sm)",
    },
    {
      variant: "inset",
      orientation: ["horizontal", "both"],
      size: "md",
      class: "pb-(--scrollbar-track-md)",
    },
    {
      variant: "inset",
      orientation: ["horizontal", "both"],
      size: "lg",
      class: "pb-(--scrollbar-track-lg)",
    },
  ],
  defaultVariants: scrollAreaDefaultVariants,
});

type ScrollAreaVariantConfig = VariantProps<typeof scrollAreaVariants>;

export type ScrollAreaVariant = NonNullable<ScrollAreaVariantConfig["variant"]>;

export type ScrollAreaSize = NonNullable<ScrollAreaVariantConfig["size"]>;

export type ScrollAreaOrientation = NonNullable<ScrollAreaVariantConfig["orientation"]>;

export type ScrollAreaVariantProps = StrictVariantProps<
  typeof scrollAreaVariants,
  keyof typeof scrollAreaDefaultVariants
>;

const scrollAreaViewportDefaultVariants = { orientation: "vertical" } as const;

export const scrollAreaViewportVariants = cva("min-h-0 flex-1 rounded-[inherit] outline-none", {
  variants: {
    /**
     * Which axes scroll. Overscroll is contained only on those axes, so wheel scrolling on the
     * other axis still chains to the page.
     */
    orientation: {
      vertical: "overscroll-y-contain",
      horizontal: "overscroll-x-contain",
      both: "overscroll-contain",
    },
  },
  defaultVariants: scrollAreaViewportDefaultVariants,
});

export type ScrollAreaViewportVariantProps = StrictVariantProps<
  typeof scrollAreaViewportVariants,
  keyof typeof scrollAreaViewportDefaultVariants
>;
export const scrollAreaCornerVariants = cva("pointer-events-none bg-transparent");

const scrollAreaScrollbarDefaultVariants = {
  visibility: "auto",
  size: "md",
} as const;

/**
 * Scrollbar track variants.
 *
 * - `visibility`: `auto` hides the scrollbar at rest (`opacity-0` + `pointer-events-none`) and
 *   reveals it on hover/scroll (`data-hovering` / `data-scrolling`); `always` keeps it permanently
 *   visible.
 * - `size`: propel scrollbar scale — `sm` 8 px track / 2 px pad → 4 px thumb, `md` 10 / 2 → 6, `lg`
 *   12 / 2 → 8. Matches native `scrollbar-*` utilities. Gutter width stays stable across states (no
 *   rest→hover morph); Figma's end-hugged Default is intentionally not mirrored.
 *
 * Track stays transparent (specs + in-product example). Contrast changes live on the thumb tokens.
 */
export const scrollAreaScrollbarVariants = cva(
  [
    // Hover fades in over 150ms; scroll reveal snaps (Base UI sample: data-scrolling duration 0).
    "flex touch-none transition-opacity duration-150 ease-out select-none data-scrolling:duration-0",
    "data-[orientation=horizontal]:flex-col data-[orientation=vertical]:flex-row",
  ],
  {
    variants: {
      /**
       * `auto` — hidden at rest, visible on hover or while scrolling. `always` — permanently
       * visible.
       */
      visibility: {
        // Match Base UI hover-reveal: invisible rails must not steal edge hits.
        auto: [
          "pointer-events-none opacity-0",
          "data-hovering:pointer-events-auto data-hovering:opacity-100",
          "data-scrolling:pointer-events-auto data-scrolling:opacity-100",
        ],
        always: "opacity-100",
      },
      /**
       * Stable track gutter + cross-axis pad, both riding the `--scrollbar-track-*` /
       * `--scrollbar-pad` ladder tokens (`styles/variables.css`, mirrored by
       * `internal/scrollbar-scale.ts`) rather than a raw Tailwind step: `sm` — 8 → 4, `md` — 10 →
       * 6, `lg` — 12 → 8. Long-axis keeps a 2 px breath (`py-0.5` / `px-0.5`).
       */
      size: {
        sm: [
          "data-[orientation=vertical]:w-(--scrollbar-track-sm) data-[orientation=vertical]:px-(--scrollbar-pad) data-[orientation=vertical]:py-0.5",
          "data-[orientation=horizontal]:h-(--scrollbar-track-sm) data-[orientation=horizontal]:px-0.5 data-[orientation=horizontal]:py-(--scrollbar-pad)",
        ],
        md: [
          "data-[orientation=vertical]:w-(--scrollbar-track-md) data-[orientation=vertical]:px-(--scrollbar-pad) data-[orientation=vertical]:py-0.5",
          "data-[orientation=horizontal]:h-(--scrollbar-track-md) data-[orientation=horizontal]:px-0.5 data-[orientation=horizontal]:py-(--scrollbar-pad)",
        ],
        lg: [
          "data-[orientation=vertical]:w-(--scrollbar-track-lg) data-[orientation=vertical]:px-(--scrollbar-pad) data-[orientation=vertical]:py-0.5",
          "data-[orientation=horizontal]:h-(--scrollbar-track-lg) data-[orientation=horizontal]:px-0.5 data-[orientation=horizontal]:py-(--scrollbar-pad)",
        ],
      },
    },
    defaultVariants: scrollAreaScrollbarDefaultVariants,
  },
);

type ScrollAreaScrollbarVariantConfig = VariantProps<typeof scrollAreaScrollbarVariants>;

/**
 * Controls when the scrollbar track is visible.
 *
 * @default "auto"
 */
export type ScrollAreaScrollbarVisibility = NonNullable<
  ScrollAreaScrollbarVariantConfig["visibility"]
>;

/**
 * Scrollbar gutter size (propel scrollbar scale). Stable full gutter; cross-axis pad matches native
 * `scrollbar-*`: `sm` — 8 px / 2 → 4 px thumb; `md` — 10 / 2 → 6; `lg` — 12 / 2 → 8. The long axis
 * keeps its own fixed 2 px breath regardless of size.
 *
 * @default "md"
 */
export type ScrollAreaScrollbarSize = NonNullable<ScrollAreaScrollbarVariantConfig["size"]>;

export type ScrollAreaScrollbarVariantProps = StrictVariantProps<
  typeof scrollAreaScrollbarVariants,
  keyof typeof scrollAreaScrollbarDefaultVariants
>;

/** Scrollbar thumb: pill on `--scrollbar-thumb*`, darker on hover / while dragging. */
export const scrollAreaThumbVariants = cva(
  "flex-1 rounded-full bg-scrollbar-thumb transition-colors hover:bg-scrollbar-thumb-hover active:bg-scrollbar-thumb-active",
);
