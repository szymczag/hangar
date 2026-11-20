import { cva, cx, type VariantProps } from "class-variance-authority";

import { nodeSlotClass } from "../../internal/node-slot";
import { surfaceVariants } from "../../internal/surface";
import { type StrictVariantProps } from "../../internal/variant-props";

// Toast is a structural overlay primitive. Base UI drives every interactive state
// (expanded/limited/swipe/starting/ending transition styles) as data attributes, so
// the atomic parts expose no styling axes (variant/variant/size). The cva pairings
// below hold the static chrome so each part is styled in one place, with no
// `className` at the boundary. The behavior-only roles (Provider, Portal) render no
// element and carry no styling — they live in `components/toast`.

// The viewport is just the fixed anchor box — each `Toast` positions itself with
// `absolute` (see `toastVariants`), Base UI's documented stacking pattern (its
// "Stacking and animations" docs), so the viewport itself needs no flex/gap.
//
// It does still need a *box*, though: absolutely-positioned children contribute no
// height, so without one the viewport collapses to 340×0 and the F6 focus ring below
// draws a hairline under the stack instead of a ring around it. `--toast-frontmost-height`
// is set inline on this element by Base UI's `Toast.Viewport`, and the cards stack upward
// from the viewport's `bottom: 0`, so matching it lines the box up with the frontmost card.
// The `0px` fallback keeps it collapsed when the queue is empty (and in the `elements`
// showcase story, which pins the var itself — rule 2b).
//
// No `outline-none` reset here: Tailwind v4's `outline-none` sets `--tw-outline-style: none`,
// which `focus-visible:outline-md` then resolves *through* (it emits
// `outline-style: var(--tw-outline-style)`), so pairing the two silently suppressed the very
// ring it was meant to leave alone. Nothing needs resetting — the UA outline is itself
// `:focus-visible`-gated.
export const toastViewportVariants = cva(
  cx(
    "fixed inset-e-4 bottom-4 z-60 w-85 max-w-[calc(100vw-2rem)] rounded-lg",
    "h-[var(--toast-frontmost-height,0px)]",
    "focus-visible:outline-md focus-visible:outline-offset-2 focus-visible:outline-accent-strong",
  ),
);

// Collapsed: the frontmost toast (`--toast-index: 0`) sits full-size at the front; each
// toast behind it peeks out and scales down by index, per Figma's "up to 3 cards
// visually shown, rear cards scaled down" (node 43:5246). Expanded (`data-expanded`,
// set while the viewport is hovered/focused): every toast un-stacks into a vertical
// list with an 8px gap, per Figma's "8 px gap between them" (node 43:5261) — `--gap`/
// `--peek` both use that token, since it's the only stacking distance the spec gives.
// `--scale`'s 10%-per-card falloff is Base UI's own default, not a Figma number — the
// spec only says "scaled down" with no figure, so this is a placeholder pending a
// precise value from design. Transform math and the swipe/starting/ending states are
// ported from Base UI's own reference implementation (`@base-ui/react/toast` docs,
// "Stacking and animations") rather than hand-derived, since it already composes
// correctly with swipe-to-dismiss.
//
// `--toast-index`/`--toast-offset-y`/`--toast-swipe-movement-*`/`--toast-height` are
// normally set inline by Base UI's `Toast.Root`/`Toast.Viewport` — every reference to
// one carries a fallback (`,0`/`,0px`/`,auto`) so the card still renders sanely (as
// index 0, un-offset, natural height) when the `elements` showcase story renders it
// directly with no Base UI behind it (rule 2b).
export const toastVariants = cva(
  cx(
    surfaceVariants({ elevation: "raised", radius: "lg" }),
    "flex items-start gap-1.5 px-3 py-3",
    "[--gap:0.5rem] [--peek:0.5rem] [--scale:calc(max(0,1-(var(--toast-index,0)*0.1)))]",
    "[--height:var(--toast-frontmost-height,var(--toast-height,auto))] [--shrink:calc(1-var(--scale))]",
    "[--offset-y:calc(var(--toast-offset-y,0px)*-1+(var(--toast-index,0)*var(--gap)*-1)+var(--toast-swipe-movement-y,0px))]",
    // `select-none` matches Base UI's reference (keeps swipe-to-dismiss from starting a text
    // selection on the card). Content re-enables selection below so a long failure reason on an
    // 8s danger toast can still be copied.
    "absolute inset-e-0 bottom-0 z-[calc(1000-var(--toast-index,0))] w-full origin-bottom select-none",
    "h-(--height) data-expanded:[height:var(--toast-height,auto)]",
    "[transform:translateX(var(--toast-swipe-movement-x,0px))_translateY(calc(var(--toast-swipe-movement-y,0px)-(var(--toast-index,0)*var(--peek))-(var(--shrink)*var(--height))))_scale(var(--scale))]",
    "data-expanded:[transform:translateX(var(--toast-swipe-movement-x,0px))_translateY(var(--offset-y))]",
    // Ambient (non-swipe) enter/exit: diagonal, toward/from the inline-end/bottom corner it's
    // anchored to, per Figma's "slide in from the right bottom edge ... exit by sliding back out
    // to the right bottom edge" (node 43:5229). Base UI's own reference CSS only slides vertically
    // here (horizontal motion is limited to user-initiated swipe-dismiss); the 10% horizontal
    // component is our own addition to match the spec's diagonal direction. `rtl:` flips the
    // physical X so motion still tracks the logical inline-end anchor (`inset-e-4`).
    "data-starting-style:[transform:translateX(10%)_translateY(150%)]",
    "rtl:data-starting-style:[transform:translateX(-10%)_translateY(150%)]",
    "[&[data-ending-style]:not([data-limited]):not([data-swipe-direction])]:[transform:translateX(10%)_translateY(150%)]",
    "rtl:[&[data-ending-style]:not([data-limited]):not([data-swipe-direction])]:[transform:translateX(-10%)_translateY(150%)]",
    "data-ending-style:opacity-0 data-limited:opacity-0",
    "data-ending-style:data-[swipe-direction=up]:[transform:translateY(calc(var(--toast-swipe-movement-y,0px)-150%))]",
    "data-ending-style:data-[swipe-direction=down]:[transform:translateY(calc(var(--toast-swipe-movement-y,0px)+150%))]",
    "data-ending-style:data-[swipe-direction=left]:[transform:translateX(calc(var(--toast-swipe-movement-x,0px)-150%))_translateY(var(--offset-y))]",
    "data-ending-style:data-[swipe-direction=right]:[transform:translateX(calc(var(--toast-swipe-movement-x,0px)+150%))_translateY(var(--offset-y))]",
    // Invisible hit-area sliver spanning the gap below each card, so hovering across
    // the stack doesn't momentarily leave the viewport's hoverable area and collapse
    // it mid-hover. It needs BOTH inline insets: `inset-e-0` alone leaves an
    // `absolute` box with no width to shrink-to-fit around empty `content: ''`, i.e.
    // a 0px-wide sliver that bridges nothing.
    "after:absolute after:inset-s-0 after:inset-e-0 after:top-full after:h-[calc(var(--gap)+1px)] after:content-['']",
    "[transition:transform_0.5s_cubic-bezier(0.22,1,0.36,1),opacity_0.5s,height_0.15s]",
    // Figma's guidance is explicit: "Don't animate toasts when prefers-reduced-motion is set —
    // show/hide immediately." Dropping the transition makes every state change (position,
    // opacity, height) apply instantly instead of tweening.
    "motion-reduce:transition-none",
  ),
);

// `data-behind` (set on the frontmost toast's siblings while collapsed) fades out a
// rear card's content so a taller toast's overflowing text doesn't visibly poke out
// from behind the front card — Base UI's documented pairing for this ("Stacking and
// animations": "`data-behind` ... pairs with `data-expanded` so content fades back in
// when the viewport expands"). The `data-expanded:data-behind:opacity-100` override is
// a compound (two-attribute) selector so it deterministically outweighs the plain
// `data-behind:opacity-0` rule regardless of utility source order — without it, a
// rear card stays invisible even once the stack expands on hover.
//
// `overflow-hidden` is scoped to collapsed-behind only (`data-behind:not-data-expanded`):
// the action cluster uses `-ms-2` so its hover pill bleeds flush with the title, and an
// always-on clip was cutting that wash on the inline-start edge (front card and expanded
// stack). Collapsed rear cards still clip so taller text can't poke out past the front card.
export const toastContentVariants = cva(
  cx(
    // Re-enable text selection inside the card (root is `select-none` for swipe); users can copy
    // failure reasons from longer-lived danger/warning toasts.
    "flex min-w-0 flex-1 flex-col gap-3 transition-opacity select-text motion-reduce:transition-none",
    "data-behind:not-data-expanded:overflow-hidden",
    "data-behind:opacity-0 data-expanded:data-behind:opacity-100",
  ),
);

// The tight vertical pairing of the title and description, sitting at the top of the
// content column. A separate part so `ToastContent` can also hold a progress bar and an
// action row as siblings with the wider `gap-3` rhythm, while title+description keep a
// closer `gap-1`.
export const toastTextGroupVariants = cva("flex flex-col gap-1");

export const toastTitleVariants = cva("text-body-sm-medium text-primary");

export const toastDescriptionVariants = cva("text-body-xs-regular text-tertiary");

// The full-width action row beneath the text/progress (Figma node 1146-61689). Holds the
// inline-start `ToastActionGroup` cluster and an optional inline-end `ToastAction`.
export const toastActionsVariants = cva("flex w-full gap-1.5");

// The inline-start cluster of 1–2 plain action buttons. Grows to fill the row so a
// trailing `ToastAction` pins to the inline-end edge. `-ms-2` pulls each button's
// transparent `px-2` pill flush with the title text while letting the hover fill bleed
// toward the inline-start. RTL-safe via logical utilities.
export const toastActionGroupVariants = cva("-ms-2 flex min-w-0 flex-1 items-center gap-1.5");

// Shared action-button styling, straight from Figma's "Buttons" sub-frame: a 24px-tall
// pill with a 40px min width, `md` radius, 13px medium secondary text, transparent
// background that fills on hover. Used for both the left cluster and the right action.
export const toastActionVariants = cva(
  cx(
    "inline-flex h-6 min-w-10 shrink-0 cursor-pointer items-center justify-center gap-1 rounded-md px-2",
    "text-body-xs-medium text-secondary outline-none",
    "bg-layer-transparent transition-colors hover:bg-layer-transparent-hover active:bg-layer-transparent-active",
    "focus-visible:ring-2 focus-visible:ring-accent-strong",
  ),
);

// The positioned slot that pins the dismiss `IconButton` to the toast's inline-end corner. Holds
// only the 4px corner offset (`absolute inset-e-1 top-1`) against the (absolutely) positioned
// toast card; the button's chrome (size/radius/hover) comes from the composed `IconButton`.
export const toastCloseGroupVariants = cva("absolute inset-e-1 top-1");

// Status-icon slot: a single styled `<span>` that sizes and variant-colors a bare `<svg>` glyph
// child via the shared node-slot class (`fill="currentColor"` inherits the per-variant color). The
// slot is the only variant-colored element; surface/border/text stay neutral, matching Figma.
// `mt-0.5` nudges it 2px down so it aligns with the title baseline when the toast root uses
// `items-start` — eliminates the need for a wrapper span.
export const toastStatusIconVariants = cva(
  cx(nodeSlotClass, "mt-0.5 size-4 [--node-size:var(--control-glyph-lg)]"),
  {
    variants: {
      variant: {
        success: "text-icon-success-primary",
        danger: "text-icon-danger-primary",
        info: "text-icon-info-primary",
        warning: "text-icon-warning-primary",
        neutral: "text-icon-tertiary",
      },
    },
  },
);

export type ToastVariant = NonNullable<VariantProps<typeof toastStatusIconVariants>["variant"]>;
export type ToastStatusIconVariantProps = StrictVariantProps<typeof toastStatusIconVariants>;
