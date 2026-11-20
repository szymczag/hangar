import { cva, cx, type VariantProps } from "class-variance-authority";

import { nodeSlotClass } from "../../internal/node-slot";
import { overlayActionsClass, overlayCloseClass } from "../../internal/overlay-frame";
import { type StrictVariantProps } from "../../internal/variant-props";

// Drawer styles its edge-anchored parts here, one place, with no `className` at
// the boundary. Base UI drives open/closed and swipe state as data attributes.
// Axes: `variant` (inline layout column vs overlay floating panel), `side` (anchor
// edge), `size` (panel width). Shared overlay surfaces — backdrop, title,
// description — live in `internal/` and are grafted in `components`. Behavior-only
// roles (Root, Provider, Indent, IndentBackground, SwipeArea, Portal, Trigger)
// render no styled element and carry no styling.

const drawerViewportDefaultVariants = {
  variant: "inline",
} as const;

// Auto portal host for `variant="inline"` when no `container` is passed. Absolute fill of the
// nearest positioned ancestor (`relative` parent) so the panel overlays without pushing siblings.
// `pointer-events-none` keeps an empty host from blocking the page when the drawer is closed.
export const drawerInlineHostVariants = cva("pointer-events-none absolute inset-0 z-50");

// Portal root inside the host / consumer container — fills the positioned layer.
export const drawerInlinePortalVariants = cva("h-full min-h-0");

// Overlay: fixed to the viewport (body portal). Contained / inline: absolute within a portal parent.
// `pointer-events-none` lets non-modal pages stay interactive under the transparent layer; the popup
// re-enables hits via `pointer-events-auto` (Base UI non-modal pattern).
export const drawerViewportVariants = cva("pointer-events-none", {
  variants: {
    variant: {
      overlay: "fixed inset-0 z-50",
      contained: "absolute inset-0 z-50",
      inline: "absolute inset-0 z-50",
    },
  },
  defaultVariants: drawerViewportDefaultVariants,
});

export type DrawerViewportVariant = NonNullable<
  VariantProps<typeof drawerViewportVariants>["variant"]
>;
export type DrawerViewportVariantProps = StrictVariantProps<
  typeof drawerViewportVariants,
  keyof typeof drawerViewportDefaultVariants
>;

const drawerPopupDefaultVariants = {
  size: "sm",
  variant: "inline",
} as const;

// `variant`:
// - inline — flush edge column absolutely positioned inside a `relative` parent (Figma Type=Inline
//   chrome). Does not push siblings. Prefer `size="sm"`.
// - overlay — floating card fixed to the viewport (body portal). Prefer `md` / `lg`.
// - contained — same card chrome as overlay, absolutely positioned inside a portal container
//   (parent must be positioned, e.g. `relative` main shell under a topnav).
// `side` is the anchor edge; slide endpoints follow it. `size` is width only
// (sm 358 / md 800 / lg 1024).
export const drawerPopupVariants = cva(
  cx(
    // Re-enable hits on the panel; viewport is `pointer-events-none` so non-modal pages stay usable.
    "pointer-events-auto flex flex-col outline-none",
    // `surface-1` is the on-top-of-page panel surface every other overlay uses (the shared
    // `internal/surface` recipe: menus, toast, toolbar). `layer-1` is an interactive
    // control fill (it carries hover/active/selected variants), wrong for a static panel.
    "bg-surface-1 transition-transform duration-200",
  ),
  {
    variants: {
      variant: {
        inline: "absolute z-50",
        overlay: "fixed z-50",
        contained: "absolute z-50",
      },
      side: {
        end: "data-ending-style:translate-x-full data-starting-style:translate-x-full",
        start: "data-ending-style:-translate-x-full data-starting-style:-translate-x-full",
      },
      size: {
        sm: "w-[358px]",
        md: "w-200",
        lg: "w-256",
      },
    },
    compoundVariants: [
      // Inline: flush leading-edge chrome (Figma Type=Inline drawer) — absolute in parent.
      // Cap to the positioned parent so a wide size never overflows the shell.
      {
        variant: "inline",
        side: "end",
        class: "inset-y-0 inset-e-0 max-w-full border-s-sm border-subtle",
      },
      {
        variant: "inline",
        side: "start",
        class: "inset-y-0 inset-s-0 max-w-full border-e-sm border-subtle",
      },
      // Overlay: inset floating card on the viewport — tight to the edge; cap to 90vw.
      {
        variant: "overlay",
        side: "end",
        class:
          "inset-y-2 inset-e-2 max-w-[90vw] rounded-lg border-sm border-subtle shadow-direction-left",
      },
      {
        variant: "overlay",
        side: "start",
        class:
          "inset-y-2 inset-s-2 max-w-[90vw] rounded-lg border-sm border-subtle shadow-direction-right",
      },
      // Contained: same card chrome as overlay, absolute in a portal parent — cap to that shell.
      {
        variant: "contained",
        side: "end",
        class:
          "inset-y-2 inset-e-2 max-w-[calc(100%-1rem)] rounded-lg border-sm border-subtle shadow-direction-left",
      },
      {
        variant: "contained",
        side: "start",
        class:
          "inset-y-2 inset-s-2 max-w-[calc(100%-1rem)] rounded-lg border-sm border-subtle shadow-direction-right",
      },
    ],
    defaultVariants: drawerPopupDefaultVariants,
  },
);

type DrawerPopupVariantConfig = VariantProps<typeof drawerPopupVariants>;
export type DrawerPopupVariant = NonNullable<DrawerPopupVariantConfig["variant"]>;
export type DrawerPopupSide = NonNullable<DrawerPopupVariantConfig["side"]>;
export type DrawerPopupSize = NonNullable<DrawerPopupVariantConfig["size"]>;
export type DrawerPopupVariantProps = StrictVariantProps<
  typeof drawerPopupVariants,
  keyof typeof drawerPopupDefaultVariants
>;

const drawerContentDefaultVariants = {
  size: "sm",
} as const;

// Padded inner stack: Figma gap-6 between header / body / footer. Padding follows
// size — sm p-4, md/lg px-8 py-7.
export const drawerContentVariants = cva("flex min-h-0 flex-1 flex-col gap-6", {
  variants: {
    size: {
      sm: "p-4",
      md: "px-8 py-7",
      lg: "px-8 py-7",
    },
  },
  defaultVariants: drawerContentDefaultVariants,
});

export type DrawerContentSize = NonNullable<VariantProps<typeof drawerContentVariants>["size"]>;
export type DrawerContentVariantProps = StrictVariantProps<
  typeof drawerContentVariants,
  keyof typeof drawerContentDefaultVariants
>;

// The drawer's top region (Figma "header"): start cluster + end actions on one row.
export const drawerHeaderVariants = cva("flex items-start justify-between gap-3");

// Narrow title cluster: optional leading icon + title/description. Figma gap-1.
export const drawerHeaderStartVariants = cva("flex min-w-0 flex-1 items-start gap-1");

// Decorative title-leading glyph (Figma 20px frame / 14px icon). Interactive leading
// controls use `IconButton` inside `DrawerHeaderStart` instead.
export const drawerHeaderIconVariants = cva(
  cx(nodeSlotClass, "mt-0.5 size-5 text-icon-secondary [--node-size:var(--control-glyph-xs)]"),
);

// Icon-button toolbars at the header's inline-start or inline-end (Figma gap-3).
// Header `justify-between` pins the two clusters to opposite edges.
export const drawerHeaderActionsVariants = cva("flex items-center gap-3", {
  variants: {
    side: {
      start: "min-w-0",
      end: "shrink-0",
    },
  },
});

type DrawerHeaderActionsVariantConfig = VariantProps<typeof drawerHeaderActionsVariants>;
export type DrawerHeaderActionsSide = NonNullable<DrawerHeaderActionsVariantConfig["side"]>;
export type DrawerHeaderActionsVariantProps = StrictVariantProps<
  typeof drawerHeaderActionsVariants
>;

// The stacked title + description inside the header start. `min-w-0` lets a long title
// wrap instead of pushing the corner close off the row. Figma gap is spacing/0.5.
export const drawerHeaderContentVariants = cva("flex min-w-0 flex-1 flex-col gap-0.5");

// The drawer's main content region (Figma "body"). Grows to fill the space between
// the header and footer and scrolls its overflow. Layout/scroll only — text tokens
// belong on Title/Description or consumer content (same as Dialog body).
export const drawerBodyVariants = cva("flex min-h-0 flex-1 flex-col gap-2 overflow-auto");

// The drawer's footer actions region (Figma "footer"). Actions sit at the inline-end.
export const drawerFooterVariants = cva(cx(overlayActionsClass, "items-center"));

// Corner dismiss chrome (20×20 ghost), matching `alertDialogCloseVariants`. `overlayCloseClass` is
// chrome only — no box — so without a size here the styled part shrink-wraps its glyph and lands
// under WCAG 2.5.8's 24px floor. `before:` synthesizes the 24px pointer target on the 20px box
// (IconButton `xs` rung pattern). Glyph size comes from the `<Icon />` the caller passes: an
// `Icon`'s own `size` variant sets `--node-size` on its own span, which shadows any value set here.
export const drawerCloseVariants = cva(
  cx(
    overlayCloseClass,
    "relative size-5 rounded-sm before:absolute before:-inset-0.5 before:-z-10 before:content-['']",
  ),
);
