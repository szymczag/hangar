import { cva, cx, type VariantProps } from "class-variance-authority";

import { nodeSlotClass } from "../../internal/node-slot";
import { overlayCloseClass } from "../../internal/overlay-frame";
import { type StrictVariantProps } from "../../internal/variant-props";

// AlertDialog is always modal: outside presses are ignored; Escape cancels the topmost alert.
// Explicit close controls (actions, corner dismiss) are also supported. Base UI drives every interactive state (open/closed, starting/ending transition styles)
// as data attributes. The one design axis the spec calls out is the leading icon badge's intent
// (danger / warning / info / success), which `AlertDialogIcon` exposes as a required `variant`.
// Alert backdrop follows the 25% black scrim in the updated product reference.

export const alertDialogViewportVariants = cva(
  "fixed inset-0 z-50 flex items-end justify-center p-4 sm:items-center",
);

// Popup: fixed 600px card (Figma node 5988-2394). No padding — Body and Actions own their
// gutters because Figma pads them asymmetrically (Body 20/20/12, Actions 12/20/20) so the two
// stacked frames read as one surface with no divider. `relative` + `overflow-clip` host the
// absolute corner dismiss. Height caps at min(740px, viewport−gutter) so short screens never
// spill (Dialog Modal pattern); 740 = Figma body max 680 + actions chrome (12 + 28 + 20).
export const alertDialogPopupVariants = cva(
  cx(
    "relative flex max-h-[min(740px,calc(100dvh-2rem))] w-150 max-w-[calc(100vw-2rem)] flex-col overflow-clip",
    "rounded-lg border-sm border-subtle bg-surface-1 shadow-raised-300 outline-none",
    "origin-(--transform-origin) transition-[opacity,transform] duration-200 motion-reduce:transition-none",
    "data-starting-style:scale-95 data-starting-style:opacity-0",
    "data-ending-style:scale-95 data-ending-style:opacity-0",
  ),
);

// Body: padded content stack (icon → intro → optional fields). Figma pads the top
// frame 20px on top/sides and 12px on the bottom — the bottom half of the 24px body→actions
// seam lives on Actions. `max-h` 680px (Figma), further clamped to viewport−gutter−footer
// (footer = 12 + 28 + 20 = 60px) so actions stay visible under the popup cap. `overflow-x-clip`
// keeps overflow-x from computing to `auto`; the flex column + 16px gap live on the inner
// clipper so wide content cannot grow the scrollport's scrollWidth (see `ScrollportXClip`).
export const alertDialogBodyVariants = cva(
  "max-h-[min(680px,calc(100dvh-2rem-3.75rem))] min-h-0 min-w-0 overflow-x-clip overflow-y-auto overscroll-contain px-5 pt-5 pb-3",
);

/**
 * Inner clipper for `AlertDialogBody` — layout stack only; clip + ring bleed come from
 * `ScrollportXClip`.
 */
export const alertDialogBodyClipVariants = cva("flex flex-col gap-4");

// Header: stacks the leading icon badge above the intro (title + description) with the Figma
// 16px gap. No end padding: the intro spans the full 560px content width in Figma, and the
// 36px badge row is what shares the top band with the corner dismiss, so nothing collides.
export const alertDialogHeaderVariants = cva("flex flex-col gap-4 max-sm:text-center");

// Icon: intent badge — soft tinted surface + 20px glyph via node-slot. Required
// `variant` states the confirmation's intent. Decorative (`aria-hidden` on the part).
// `self-start` keeps the badge hug-sized inside the Header's column flex (default
// `align-items: stretch` would paint a full-bleed tint bar).
export const alertDialogIconVariants = cva(
  cx(
    nodeSlotClass,
    "inline-flex items-center justify-center self-start rounded-lg p-2 [--node-size:var(--control-glyph-2xl)] max-sm:size-12 max-sm:self-center",
  ),
  {
    variants: {
      variant: {
        danger: "bg-danger-subtle-hover text-icon-danger-secondary",
        warning: "bg-warning-secondary text-icon-warning-secondary",
        info: "bg-info-subtle-1 text-icon-info-secondary",
        success: "bg-success-subtle-1 text-icon-success-secondary",
      },
    },
  },
);

// Intro: title over description with the Figma 6px gap. `wrap-break-word` mirrors the Figma
// frame's word-break so an unbroken token (a URL, a slug) wraps instead of clipping under the
// popup's overflow-clip. `first:pe-10` clears the corner dismiss only when the intro is the
// header's first child (no badge); with the badge above it, the intro keeps Figma's full 560px.
export const alertDialogIntroVariants = cva(
  "flex min-w-0 flex-col gap-1.5 wrap-break-word first:pe-10 max-sm:first:ps-10",
);

// Title: Figma font/h6/semibold (16px / 1.3 / 600), text/primary.
export const alertDialogTitleVariants = cva("text-h6-semibold text-primary");

// Description: Figma font/body-sm/regular (14px / 1.54 / 450), text/secondary.
export const alertDialogDescriptionVariants = cva("text-body-sm-regular text-secondary");

// Below 640px, keep the legacy bottom-aligned card, centered intro/48px badge, and reversed
// full-width action column. Desktop geometry remains the fixed-width Figma composition.

// Actions: end-aligned footer row, 12px button gap, no divider (Figma draws the body and the
// actions as two frames on one surface). Pads 12px on top / 20px sides + bottom so the buttons
// sit 24px under the last body line and 20px off the popup edge. `shrink-0` keeps CTAs pinned
// when the body scrolls under the popup max-height.
// `flex-wrap` lets a footer with more or longer buttons than Figma's three fall onto a second
// row instead of clipping past the popup edge.
const alertDialogActionsDefaultVariants = { layout: "inline" } as const;

export const alertDialogActionsVariants = cva(
  cx(
    "flex shrink-0 flex-wrap items-center gap-3 px-5 pt-3 pb-5 max-sm:flex-col-reverse max-sm:items-stretch",
    "[&_button[data-size=md][data-variant=ghost]]:text-body-sm-medium [&_button[data-size=md][data-variant=secondary]]:text-body-sm-medium",
  ),
  {
    variants: { layout: { inline: "justify-end", split: "justify-between" } },
    defaultVariants: alertDialogActionsDefaultVariants,
  },
);

export type AlertDialogActionsLayout = NonNullable<
  VariantProps<typeof alertDialogActionsVariants>["layout"]
>;
export type AlertDialogActionsVariantProps = StrictVariantProps<
  typeof alertDialogActionsVariants,
  keyof typeof alertDialogActionsDefaultVariants
> & {
  /**
   * End-align actions in one row, or separate a leading action from an action group.
   *
   * @default "inline"
   */
  layout?: AlertDialogActionsLayout;
};

export const alertDialogActionGroupVariants = cva(
  "flex flex-wrap items-center justify-end gap-3 max-sm:flex-col-reverse max-sm:items-stretch",
);

export const alertDialogBackdropVariants = cva(
  "fixed inset-0 z-50 bg-black/25 transition-opacity duration-200 data-closed:pointer-events-none data-ending-style:pointer-events-none data-ending-style:opacity-0 data-starting-style:opacity-0 motion-reduce:transition-none",
);

// Corner dismiss chrome (20×20 ghost). Positioned by `AlertDialogCloseGroup`. Glyph size comes
// from the `<Icon size="sm" />` the caller passes — set it at the call site, not here: an
// `Icon`'s own `size` variant sets `--node-size` on its own span, which shadows any value set here.
// `before:` synthesizes a 24px hit target on the 20px box (IconButton `xs` rung pattern, WCAG 2.5.8).
export const alertDialogCloseVariants = cva(
  cx(
    overlayCloseClass,
    "relative size-5 rounded-sm before:absolute before:-inset-0.5 before:-z-10 before:content-['']",
  ),
);

// Pins the dismiss control to the popup's top-end corner (Figma 16px inset, 20×20 control).
// `flex` so the inline-flex button sits at the group's top edge instead of on a 24px line box
// (which would drop it 2px). `z-10` keeps it above scrolling body content (Dialog Modal pattern).
export const alertDialogCloseGroupVariants = cva("absolute inset-e-4 top-4 z-10 flex");

export type AlertDialogIconVariant = NonNullable<
  VariantProps<typeof alertDialogIconVariants>["variant"]
>;
export type AlertDialogIconVariantProps = StrictVariantProps<typeof alertDialogIconVariants>;
