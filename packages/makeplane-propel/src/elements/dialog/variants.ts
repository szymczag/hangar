import { cva, cx, type VariantProps } from "class-variance-authority";

import { nodeSlotClass } from "../../internal/node-slot";
import { type StrictVariantProps } from "../../internal/variant-props";

// Dialog is a structural overlay primitive. Base UI drives every interactive state (open/closed,
// starting/ending transition styles) as data attributes. `size` is the width axis: it picks the
// popup width and, through the ready-mades, the default gutter of Main / Actions / Aside (16 px,
// 48 px at `full`). Compactness is a second axis only because `size` is already taken — `density`
// (`comfortable` · `compact`), the same name CheckboxGroup uses. `compact` keeps the 16 px gutter
// at every size, including `full`, so a viewport-filling picker is not forced into wizard spacing.
// Every other structural chrome is baked in. Title/Description diverge from the shared overlay
// chrome (h5-medium + body-xs tertiary), so they live here rather than on `OverlayTitle`/
// `OverlayDescription`. Backdrop stays shared `internal/`.

// DialogViewport: popups hang from an 80 px top edge and keep the same 80 px below once they hit
// the ceiling (`py-20` here, `max-h-[calc(100dvh-10rem)]` on the popup). Not the alert dialog's
// centring viewport — a dialog's title must not move when its content grows.
export const dialogViewportVariants = cva(
  "fixed inset-0 z-50 flex items-start justify-center px-4 py-20",
);

const dialogPopupDefaultVariants = {
  size: "md",
  height: "auto",
} as const;

export const dialogPopupVariants = cva(
  cx(
    // chrome — relative so the absolute close group anchors; no padding/gap;
    // `DialogToolbar` / `DialogMain` / `DialogActions` own their regions so chrome
    // borders sit flush to the popup.
    "relative flex max-h-[calc(100dvh-10rem)] max-w-[calc(100vw-2rem)] flex-col overflow-clip rounded-xl border-sm border-subtle bg-surface-1 shadow-raised-300 outline-none",
    // open/close animation — drop the tween when prefers-reduced-motion is on (Toast pattern)
    "origin-(--transform-origin) transition-[opacity,transform] duration-200 motion-reduce:transition-none",
    "data-starting-style:scale-95 data-starting-style:opacity-0",
    "data-ending-style:scale-95 data-ending-style:opacity-0",
  ),
  {
    variants: {
      // Width axis. xs 480 · sm 576 · md 672 · lg 800 · xl 1000 · full = viewport − 160.
      // Height is content-sized up to the ceiling, except `full`, which pins it there so panes
      // fill the popup and the footer does not move between steps.
      size: {
        xs: "w-120",
        sm: "w-144",
        md: "w-168",
        lg: "w-200",
        xl: "w-250",
        full: "h-[calc(100dvh-10rem)] w-[calc(100vw-10rem)]",
      },
      // Height axis for split chrome that switches panes: `fixed` is 700 px, still
      // clamped by the viewport ceiling. Do not combine with `size="full"` — that size
      // already pins height. Pinning lives on the popup, not on `DialogPanes` (`flex-1`
      // inside a content-sized card cannot hold a pixel height across tab changes).
      height: {
        auto: "",
        fixed: "h-175 min-h-0",
      },
    },
    defaultVariants: dialogPopupDefaultVariants,
  },
);

// DialogPanes: side-by-side row between the close group and the footer — `DialogAside` on the
// start side, `DialogMain` filling the rest. Flex-stretch (not percentage height) so the aside
// seam matches the taller pane, whether the popup is `full` or content-sized.
export const dialogPanesVariants = cva("flex min-h-0 flex-1 items-stretch overflow-clip");

const dialogChromeDefaultVariants = {
  size: "md",
  density: "comfortable",
} as const;

// Padding classes live only on compoundVariants so `p-4` and `p-12` never sit on the same node
// (Tailwind source order, not cva order, would otherwise pick a winner).
const dialogGutterCompounds = [
  { density: "compact" as const, class: "p-4" },
  { density: "comfortable" as const, size: "xs" as const, class: "p-4" },
  { density: "comfortable" as const, size: "sm" as const, class: "p-4" },
  { density: "comfortable" as const, size: "md" as const, class: "p-4" },
  { density: "comfortable" as const, size: "lg" as const, class: "p-4" },
  { density: "comfortable" as const, size: "xl" as const, class: "p-4" },
  { density: "comfortable" as const, size: "full" as const, class: "p-12" },
];

const dialogAsideGutterCompounds = [
  { density: "compact" as const, class: "p-4 pe-0" },
  { density: "comfortable" as const, size: "xs" as const, class: "p-4 pe-0" },
  { density: "comfortable" as const, size: "sm" as const, class: "p-4 pe-0" },
  { density: "comfortable" as const, size: "md" as const, class: "p-4 pe-0" },
  { density: "comfortable" as const, size: "lg" as const, class: "p-4 pe-0" },
  { density: "comfortable" as const, size: "xl" as const, class: "p-4 pe-0" },
  { density: "comfortable" as const, size: "full" as const, class: "p-12 pe-0" },
];

const dialogToolbarGutterCompounds = [
  { density: "compact" as const, class: "ps-4 pe-10 pt-4 pb-2" },
  { density: "comfortable" as const, size: "xs" as const, class: "ps-4 pe-10 pt-4 pb-2" },
  { density: "comfortable" as const, size: "sm" as const, class: "ps-4 pe-10 pt-4 pb-2" },
  { density: "comfortable" as const, size: "md" as const, class: "ps-4 pe-10 pt-4 pb-2" },
  { density: "comfortable" as const, size: "lg" as const, class: "ps-4 pe-10 pt-4 pb-2" },
  { density: "comfortable" as const, size: "xl" as const, class: "ps-4 pe-10 pt-4 pb-2" },
  { density: "comfortable" as const, size: "full" as const, class: "ps-12 pe-12 pt-4.5 pb-2" },
];

const dialogActionsGutterCompounds = [
  { density: "compact" as const, class: "p-4" },
  { density: "comfortable" as const, size: "xs" as const, class: "p-4" },
  { density: "comfortable" as const, size: "sm" as const, class: "p-4" },
  { density: "comfortable" as const, size: "md" as const, class: "p-4" },
  { density: "comfortable" as const, size: "lg" as const, class: "p-4" },
  { density: "comfortable" as const, size: "xl" as const, class: "p-4" },
  { density: "comfortable" as const, size: "full" as const, class: "px-12 py-4.5" },
];

const dialogSizeVariants = {
  xs: "",
  sm: "",
  md: "",
  lg: "",
  xl: "",
  full: "",
} as const;

const dialogDensityVariants = {
  comfortable: "",
  compact: "",
} as const;

const dialogAsideDefaultVariants = {
  ...dialogChromeDefaultVariants,
} as const;

// DialogAside: fixed 280 px start column inside `DialogPanes`. `self-stretch` (not `h-full`) so
// percentage height cannot collapse the rail to its content. A single child grows to fill the
// rail (`flex-1 min-h-0`) without inheriting `flex-col` — consumer rows (icon + label) keep their
// own layout. Gutter follows the popup `size` (16 px, 48 px at `full`); `density="compact"` keeps
// 16 px at `full`. `pe-0` keeps the seam on the pane edge.
// `overflow-x-clip` keeps overflow-x from computing to `auto`; the inner clipper keeps focus from
// growing scrollWidth (see `ScrollportXClip`).
export const dialogAsideVariants = cva(
  "flex min-h-0 w-70 shrink-0 flex-col self-stretch overflow-x-clip overflow-y-auto overscroll-contain border-e border-subtle",
  {
    variants: {
      size: dialogSizeVariants,
      density: dialogDensityVariants,
    },
    compoundVariants: dialogAsideGutterCompounds,
    defaultVariants: dialogAsideDefaultVariants,
  },
);

/**
 * Inner clipper for `DialogAside` — grow rules only; clip + ring bleed come from `ScrollportXClip`.
 * Carries the only-child grow rules that used to live on the aside itself, now that the aside's
 * only child is this clipper.
 */
export const dialogAsideClipVariants = cva(
  "flex min-h-0 flex-1 flex-col [&>*:only-child]:h-auto [&>*:only-child]:min-h-0 [&>*:only-child]:flex-1",
);

const dialogMainDefaultVariants = {
  ...dialogChromeDefaultVariants,
  inPanes: false,
} as const;

// DialogMain: the padded top section (progression + heading + scrollable body). Content-sized;
// `min-h-0` lets the popup's ceiling shrink it while `DialogActions` stays `shrink-0`, so the
// footer is always visible and `DialogBody` scrolls. Gutter follows the popup `size` (16 px, 48 px
// at `full`); `density="compact"` keeps 16 px at `full`. Inside `DialogPanes` it fills the width
// beside `DialogAside`. The absolute `DialogCloseGroup` overlays the top-end.
export const dialogMainVariants = cva(
  "flex min-h-0 min-w-0 flex-auto flex-col gap-4 overflow-clip",
  {
    variants: {
      size: dialogSizeVariants,
      density: dialogDensityVariants,
      inPanes: {
        true: "min-h-0 [&>*:only-child]:h-auto [&>*:only-child]:min-h-0 [&>*:only-child]:flex-1",
        false: "",
      },
    },
    compoundVariants: dialogGutterCompounds,
    defaultVariants: dialogMainDefaultVariants,
  },
);

// DialogHeader: stacks optional progression over the heading block. No close —
// dismiss lives in `DialogCloseGroup` on the popup. `pe-10` clears title/progression
// under the absolute dismiss without widening Main/Body gutters.
export const dialogHeaderVariants = cva("flex flex-col gap-4 pe-10");

// DialogProgression: back affordance + step label row.
export const dialogProgressionVariants = cva(
  "flex h-5 items-center gap-1 text-caption-md-regular text-tertiary",
);

// DialogHeading: title-over-description block. Tight 6 px gap per Figma.
export const dialogHeadingVariants = cva("flex min-w-0 flex-col gap-1.5");

// DialogTitle: h5 medium primary — dialog-specific (diverges from OverlayTitle lg).
export const dialogTitleVariants = cva("text-h5-medium text-primary");

// DialogDescription: body-xs tertiary — dialog-specific (diverges from OverlayDescription).
export const dialogDescriptionVariants = cva("text-body-xs-regular text-tertiary");

// DialogBody: scrollable slot. Grows to fill Main; scrolls vertically when content
// exceeds the popup max. `overflow-x-clip` + `min-w-0` keep overflow-x from computing to
// `auto` (trackpad sideways pan). That pair computes `clip` → `hidden`, which still allows
// focus-driven `scrollLeft` when wide children grow `scrollWidth` — so an inner
// `ScrollportXClip` keeps those children out of the scrollport's scrollable overflow.
//
// `p-0.5 -m-0.5` is ring bleed: field controls use `ring-2` focus chrome
// (`fieldControlSurfaceVariants`), and non-visible overflow clips that ink at the body's
// edge. The 2 px inset keeps the ring inside the scrollport; the matching negative
// margin cancels layout shift so Main still owns the 16/48 px gutter.
// (Create-work-item puts its title in `DialogHeader`, which has no overflow — that is
// why its focus ring looked fine while WIT/property fields in `DialogBody` did not.)
export const dialogBodyVariants = cva(
  "-m-0.5 min-h-0 min-w-0 flex-1 overflow-x-clip overflow-y-auto overscroll-contain p-0.5",
);

const dialogActionsDefaultVariants = {
  ...dialogChromeDefaultVariants,
} as const;

const dialogToolbarDefaultVariants = {
  ...dialogChromeDefaultVariants,
} as const;

// DialogToolbar: top chrome strip, sibling of `DialogMain` (not inside it). Bottom border is on
// this element so it spans the popup — same geometry as `DialogActions`' top border. Start gutter
// matches Actions (16 px, 48 px at `full`); end gutter is `pe-10` (40 px) so an end-aligned
// control clears the absolute `DialogCloseGroup`, the same clearance `DialogHeader` uses. At
// `full` the 48 px Actions gutter already clears the close. Bottom padding is 8 px so a tab
// indicator can sit on the rule. Tabs, a title row, or an end-aligned control go here;
// `DialogHeader` stays the title block inside Main.
export const dialogToolbarVariants = cva(
  "flex shrink-0 items-center justify-between gap-3 border-b border-subtle",
  {
    variants: {
      size: dialogSizeVariants,
      density: dialogDensityVariants,
    },
    compoundVariants: dialogToolbarGutterCompounds,
    defaultVariants: dialogToolbarDefaultVariants,
  },
);

// DialogActions: footer with top border. Info helper at inline-start (flex-1 via `DialogInfo`);
// action buttons follow at the inline-end with a 12 px gap. `justify-end` keeps CTAs on the
// inline-end when there is no info helper. Gutter follows the popup `size` (16 px, 48 × 18 px
// at `full`); `density="compact"` keeps 16 px at `full`.
export const dialogActionsVariants = cva(
  "flex shrink-0 items-center justify-end gap-3 border-t border-subtle",
  {
    variants: {
      size: dialogSizeVariants,
      density: dialogDensityVariants,
    },
    compoundVariants: dialogActionsGutterCompounds,
    defaultVariants: dialogActionsDefaultVariants,
  },
);

// DialogInfo: optional footer helper — decorative icon + caption.
export const dialogInfoVariants = cva(
  "flex min-w-0 flex-1 items-center gap-1 text-caption-md-regular text-tertiary",
);

// DialogInfoIcon: 14 px decorative glyph slot inside DialogInfo.
export const dialogInfoIconVariants = cva(
  cx(nodeSlotClass, "shrink-0 text-icon-tertiary [--node-size:var(--control-glyph-xs)]"),
);

// DialogCloseGroup: pins the dismiss IconButton to the popup's top inline-end
// (Figma ~15 px inset → token spacing 4 = 16 px).
export const dialogCloseGroupVariants = cva("absolute inset-e-4 top-4 z-10");

export type DialogPopupSize = NonNullable<VariantProps<typeof dialogPopupVariants>["size"]>;
export type DialogPopupHeight = NonNullable<VariantProps<typeof dialogPopupVariants>["height"]>;
export type DialogPopupVariantProps = StrictVariantProps<
  typeof dialogPopupVariants,
  keyof typeof dialogPopupDefaultVariants
>;

export type DialogDensity = NonNullable<VariantProps<typeof dialogMainVariants>["density"]>;

export type DialogAsideSize = NonNullable<VariantProps<typeof dialogAsideVariants>["size"]>;
export type DialogAsideDensity = DialogDensity;
export type DialogAsideVariantProps = StrictVariantProps<
  typeof dialogAsideVariants,
  keyof typeof dialogAsideDefaultVariants
>;

export type DialogMainSize = NonNullable<VariantProps<typeof dialogMainVariants>["size"]>;
export type DialogMainDensity = DialogDensity;
export type DialogMainVariantProps = StrictVariantProps<
  typeof dialogMainVariants,
  keyof typeof dialogMainDefaultVariants
>;

export type DialogToolbarSize = NonNullable<VariantProps<typeof dialogToolbarVariants>["size"]>;
export type DialogToolbarDensity = DialogDensity;
export type DialogToolbarVariantProps = StrictVariantProps<
  typeof dialogToolbarVariants,
  keyof typeof dialogToolbarDefaultVariants
>;

export type DialogActionsSize = NonNullable<VariantProps<typeof dialogActionsVariants>["size"]>;
export type DialogActionsDensity = DialogDensity;
export type DialogActionsVariantProps = StrictVariantProps<
  typeof dialogActionsVariants,
  keyof typeof dialogActionsDefaultVariants
>;
