import { cva, cx, type VariantProps } from "class-variance-authority";

import { type StrictVariantProps } from "../../internal/variant-props";

// "Always the same" per Figma design spec (issue #142):
// - Medium (md) border-radius
// - Inline-flex layout with centered content
// - Height, horizontal padding, font size per size step
// - Font weight
// - Single-line text (no wrapping)
// - Hover/press/disabled/loading visual treatment
// - Leading/trailing node position (inline-start / inline-end), sized per size step
//
// "Depends (adjustable)" → props: label (children), leading/trailing node, size,
// variant (Pill outline|soft|ghost), disabled, `placeholder` (an empty trigger), and which
// interactive part (Pill vs IconPill). Open state is not a prop: Base UI sets
// `data-popup-open` on a grafted Menu/Popover trigger and the cvas key off it.
// size/variant have no sensible default on elements, so they are required — no cva
// `defaultVariants`.

// Shared structural base baked into every pill container cva below.
// `align-middle`: an inline-flex box in inline flow otherwise sits on its first item's baseline,
// which an svg, an 8px disc and a 16px avatar each place differently — so a pill inside an inline
// wrapper would ride up or down with whatever leads it. Inert inside a flex row.
const pillBase =
  "inline-flex shrink-0 items-center justify-center rounded-md border-sm align-middle outline-none transition-colors focus-visible:ring-2 focus-visible:ring-accent-strong";

// Shared label-pill base (Pill): the rung's node scale and per-size height/padding/font. The
// truncation cap (224px) lives on the container cva, not here.
// No vertical padding: the fixed per-size heights own the box, and the label's line box
// (14.4–20px) already overran a `py-1` at every step — the padding was inert CSS that
// `items-center` silently absorbed.
// Glyph rides the rung tokens (14px at `xs`/`sm`, 16px at `md` — the with-text ramp). The tight 4px gap is the chip design; the side padding is the rung's at `sm` and a step narrower than a button's at `xs` and `md`.
const labelPillBase = cx(pillBase, "gap-1");

// A chip's label is a caption, and a caption does not grow with the box the way a button's
// label does: the first two steps share the 12px caption and only the box relaxes between them
// (Kumo, Fluent, Radix and Atlassian all hold 12px across their first two chip heights); the
// label steps to 13px at 28px, where a 12px caption would read a step small beside the other
// 28px rows (Button `md`, a 28px bordered control).
//
// `sm` is the comfortable chip: 24px on the rung's 8px padding, so the ink is ~36% of the box
// and the side padding ≈ the cap height — the proportion a 44px list row wants. `xs` is the dense
// step (ink ~44%, 6px sides) for tables and cards. `md` keeps its 8px sides for now.
const labelPillSize = {
  // 20px painted, 24px pointer target via the `::before` ring (WCAG 2.5.8); `pillBase` is not
  // positioned, so the step adds its own `relative` — same shape as IconPill's `xs`.
  xs: "relative h-(--control-height-xs) px-1.5 text-caption-md-regular [--node-size:var(--control-glyph-xs)] before:absolute before:-inset-0.5 before:-z-10 before:content-['']",
  sm: "h-(--control-height-sm) px-(--control-padding-x-sm) text-caption-md-regular [--node-size:var(--control-glyph-sm)]",
  md: "h-(--control-height-md) px-2 text-body-xs-regular [--node-size:var(--control-glyph-md)]",
} as const;

// ─── Containers (one styled element each) ────────────────────────────────────

export const pillVariants = cva(
  [
    labelPillBase,
    "max-w-[224px] cursor-pointer text-secondary",
    // `placeholder` (`data-placeholder`, an empty trigger) dims the label and any inherited-tint
    // glyph together. The two `not-` guards do double duty: they lift the rule's specificity above
    // a variant's `active:` / `data-popup-open:` text colour, so an empty trigger stays dim while
    // its picker is open, and they stop it matching while disabled or busy, where the variant's
    // own muted colour must win. An inherited-tint glyph paints with `currentColor`, so it dims
    // with the label and needs no rule of its own.
    "data-placeholder:not-disabled:not-aria-busy:text-placeholder",
  ],
  {
    variants: {
      size: labelPillSize,
      // Figma Pill mirrors Button variant chrome (control-chrome):
      // `outline` ≈ secondary (bordered + layer-2), `soft` ≈ tertiary (borderless + layer-3),
      // `ghost` ≈ ghost (borderless, transparent-alpha washes so it reads on any surface — for a
      // trigger whose content is its own box, e.g. an avatar stack).
      // Open (Base UI's `data-popup-open` on a grafted Menu/Popover trigger) wears each
      // variant's active look for as long as the picker is up: focus moves into the popup, so
      // `:active` / `:focus-visible` alone would leave the trigger looking closed.
      // Disabled/loading stay transparent per the pill Figma (not button's layer-disabled fill).
      variant: {
        outline: [
          "border-subtle-1 bg-layer-2",
          "hover:border-strong hover:bg-layer-2-hover",
          "active:border-strong active:bg-layer-2-active active:text-primary",
          "data-popup-open:border-strong data-popup-open:bg-layer-2-active data-popup-open:text-primary",
          "disabled:cursor-not-allowed disabled:border-subtle-1 disabled:bg-layer-transparent disabled:text-disabled",
          "aria-busy:cursor-default aria-busy:border-subtle-1 aria-busy:bg-layer-transparent aria-busy:text-disabled",
        ],
        soft: [
          "border-transparent bg-layer-3",
          "hover:bg-layer-3-hover",
          "active:bg-layer-3-active active:text-primary",
          "data-popup-open:bg-layer-3-active data-popup-open:text-primary",
          "disabled:cursor-not-allowed disabled:bg-layer-transparent disabled:text-disabled",
          "aria-busy:cursor-default aria-busy:bg-layer-transparent aria-busy:text-disabled",
        ],
        ghost: [
          "border-transparent bg-layer-transparent",
          "hover:bg-layer-transparent-hover",
          "active:bg-layer-transparent-active active:text-primary",
          "data-popup-open:bg-layer-transparent-active data-popup-open:text-primary",
          "disabled:cursor-not-allowed disabled:bg-layer-transparent disabled:text-disabled",
          "aria-busy:cursor-default aria-busy:bg-layer-transparent aria-busy:text-disabled",
        ],
      },
    },
  },
);

// No `defaultVariants` today, so every axis is required.
export type PillVariantProps = StrictVariantProps<typeof pillVariants>;
type PillVariantConfig = VariantProps<typeof pillVariants>;
export type PillVariant = NonNullable<PillVariantConfig["variant"]>;

export const iconPillVariants = cva(
  [
    pillBase,
    "cursor-pointer border-subtle-1 bg-layer-2 text-icon-secondary",
    "hover:border-strong hover:bg-layer-2-hover",
    "active:border-strong active:bg-layer-2-active",
    "data-popup-open:border-strong data-popup-open:bg-layer-2-active",
    "disabled:cursor-not-allowed disabled:border-subtle-1 disabled:bg-layer-transparent disabled:text-icon-disabled",
    "aria-busy:cursor-default aria-busy:border-subtle-1 aria-busy:bg-layer-transparent aria-busy:text-icon-disabled",
  ],
  {
    variants: {
      size: {
        // 20x20 painted, 24x24 pointer target via a transparent `::before` ring — same reasoning
        // as `IconButton`'s `xs`: an icon-only control has no label to carry the width.
        // `pillBase` is not positioned, so this step adds its own `relative`.
        xs: "relative size-(--control-height-xs) [--node-size:var(--control-glyph-xs)] before:absolute before:-inset-0.5 before:-z-10 before:content-['']",
        sm: "size-(--control-height-sm) [--node-size:var(--control-glyph-sm)]",
        md: "size-(--control-height-md) [--node-size:var(--control-glyph-md)]",
      },
    },
  },
);

type IconPillVariantConfig = VariantProps<typeof iconPillVariants>;
export type IconPillSize = NonNullable<IconPillVariantConfig["size"]>;

// No `defaultVariants` today, so every axis is required.
export type IconPillVariantProps = StrictVariantProps<typeof iconPillVariants>;

// ─── Inline parts (one element each) ─────────────────────────────────────────

// The single-line label inside a label pill. `min-w-0` lets it shrink and `truncate`
// keeps it on one line per the Figma spec.
export const pillLabelVariants = cva("min-w-0 truncate");

export type PillSize = NonNullable<PillVariantConfig["size"]>;

// ─── Connected frame ─────────────────────────────────────────────────────────

// PillGroup is the connected frame around the pills that make up one compound control — a filter
// condition ("Parent type · is · Task · ✕"), a property row (Figma "PillbuttonGroup", 9335-67960).
//
// The segments keep their own chrome and the frame owns only how they sit together — the division
// of labour `SplitButton` uses, not `ButtonGroup`'s. A ButtonGroup segment is chrome-less by
// construction, so that family needs a styled segment part of its own; a pill in a group is still
// an ordinary pill, so this frame takes plain `Pill`/`IconPill` children and there is no second
// component to learn.
//
// Figma strokes the frame AND every segment, doubling the 1px border along the outer edge. Here the
// frame carries no border: the segments' own borders overlap by 1px (Figma's own `mr:-1px`) and
// each shared edge reads as a single divider. The frame keeps the surface — a disabled or busy
// segment drops to `bg-layer-transparent`, and with nothing behind it the page would show through
// the hole.
//
// `isolate` + `z-10` lifts whichever segment is hovered, focused, or holding an open picker, so its
// darker border and its offset focus ring paint over the neighbour rather than under it: the shared
// seam always belongs to the live segment. z-index applies to a static flex item, so the segments
// need no `relative` of their own.
//
// The corner and seam selectors ask about siblings that are NOT spans, never about position. While
// a segment's picker is open, Base UI lands its own nodes as direct children of this frame — three
// `<span data-base-ui-focus-guard>`s and one `<span aria-owns>` bridge, before AND after the
// trigger — so `:first-child`/`:last-child` stop naming the outermost segments and the group's
// corners square off mid-interaction. `SplitButton` sidesteps this by never keying off
// `:last-child`, which is enough for two fixed children but not for a run of N.
// Excluding `span` rather than enumerating those attributes keeps the rule true if Base UI adds
// another node: a segment is a `<button>` (or an `<a>` via `render`), never a span.
// `GroupFocusGuards` pins both ends with a picker open.
export const pillGroupVariants = cva(
  cx(
    "isolate inline-flex items-center rounded-md bg-layer-2 align-middle",
    // Corners: only the outermost two survive, so the run reads as one control.
    "[&>*:not(span)~*]:rounded-s-none",
    "[&>*:has(~*:not(span))]:rounded-e-none",
    // Seams: collapse the doubled border to a single line.
    "[&>*:not(span)~*]:-ms-px",
    // The live segment owns the seam it shares.
    "[&>*:focus-visible]:z-10 [&>*:hover]:z-10 [&>*[data-popup-open]]:z-10",
  ),
  {
    variants: {
      // Colour-less, like `splitButtonVariants` — the axis exists so the frame declares the rung
      // its segments share, and the `components` frame hands that value down through context.
      //
      // No 20px step: a segment is contiguous with its neighbour, so that rung's transparent
      // `::before` hit ring would overlap the neighbour and void WCAG 2.5.8's spacing exception —
      // the same reason `ButtonGroupButton` and `SplitButton` stop at 24px. Figma ships a 20px
      // group; it should drop it.
      size: { sm: "", md: "" },
    },
  },
);

type PillGroupVariantConfig = VariantProps<typeof pillGroupVariants>;
export type PillGroupSize = NonNullable<PillGroupVariantConfig["size"]>;

// No `defaultVariants` today, so every axis is required.
export type PillGroupVariantProps = StrictVariantProps<typeof pillGroupVariants>;
