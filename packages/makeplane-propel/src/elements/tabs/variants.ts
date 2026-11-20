import { cva, cx, type VariantProps } from "class-variance-authority";

import { type StrictVariantProps } from "../../internal/variant-props";

// `contained` wraps the tabs in a pill and lifts the active tab onto a raised card; `underline`
// keeps them flat and slides a dark bar under the active one.
export type TabsAppearance = NonNullable<VariantProps<typeof tabsVariants>["variant"]>;

// Whether the tab row shrinks to fit its tabs (`auto`) or fills its container, splitting it into
// equal-width tabs (`full`) — mirrors Button's `stretch` axis.
export type TabsStretch = NonNullable<VariantProps<typeof tabsVariants>["stretch"]>;

// Whether the set takes its content height or fills a bounded parent.
export type TabsLayout = NonNullable<VariantProps<typeof tabsVariants>["layout"]>;

const tabsDefaultVariants = { layout: "content", stretch: "auto" } as const;

// `flex w-full`, not `inline-flex`: the root takes the width its parent gives it and keeps that
// width stable across tab switches. `inline-flex` shrink-wraps to whichever child is currently
// widest — since the active `TabsPanel` swaps content on every switch, that shrink-wrapped width
// could wobble by a few px between tabs, and inside any horizontally-centered layout (Storybook's
// `sb-main-centered`, or a consumer's own centered wrapper), that wobble visibly re-centers the
// whole component on every switch. `w-full` also covers the flex/grid-item case where a non-stretch
// parent would otherwise still size the root to content despite `display: flex`.
export const tabsVariants = cva("flex w-full max-w-full flex-col items-start gap-3", {
  variants: {
    variant: {
      contained: "",
      underline: "",
    },
    // Pass-through placeholder, like `variant` above: the root is always `w-full` regardless of
    // `stretch` (that's the row's job, not the whole set's) — this axis exists here only so the
    // canonical `TabsStretch` type derives from the root, matching `TabsAppearance`.
    stretch: {
      auto: "",
      full: "",
    },
    layout: {
      content: "",
      fill: "h-full min-h-0 flex-1",
    },
  },
  defaultVariants: tabsDefaultVariants,
});

export type TabsVariantProps = StrictVariantProps<
  typeof tabsVariants,
  keyof typeof tabsDefaultVariants
>;

export const tabsListVariants = cva("relative max-w-full overscroll-x-contain outline-none", {
  variants: {
    variant: {
      contained: "items-center gap-px rounded-lg bg-layer-3 p-0.5",
      underline: "items-start gap-px px-0.5",
    },
    // `inline-flex` shrink-wraps to the tabs (today's default); `full` fills the container instead,
    // so each `Tab`'s own `stretch: full` (`flex-1`) has a flex row to grow inside.
    stretch: {
      auto: "inline-flex",
      full: "flex w-full",
    },
  },
  // No `defaultVariants` — `stretch` only ever arrives via `TabsStretchContext`; the ready-made
  // `components/Tabs` resolves the consumer default (`"auto"`), per CLAUDE.md rule 13. Mirrors
  // `checkboxLabelVariants`.
});

export type TabsListVariantProps = StrictVariantProps<typeof tabsListVariants>;

// The horizontal scroll frame around a `TabsList` so a long tab row scrolls. It sits directly on
// the `items-start` root (`tabsVariants` above), so without an explicit `w-full` here it shrinks to
// its content regardless of what `stretch` the `TabsList` inside it asks for — this is the part
// that actually has to grow for `stretch: full` to reach the tabs at all.
export const tabsListScrollAreaVariants = cva("relative max-w-full", {
  variants: {
    stretch: {
      auto: "",
      full: "w-full",
    },
  },
  // No `defaultVariants` — see `tabsListVariants` above; `stretch` only ever arrives via
  // `TabsStretchContext`.
});

export type TabsListScrollAreaVariantProps = StrictVariantProps<typeof tabsListScrollAreaVariants>;

export const tabVariants = cva(
  // `--node-size` sizes any leading icon slot and is declared per `variant`, not here: the two
  // variants sit on different rungs (`contained` is a 24px `sm` row, `underline` a 28px `md` one),
  // so a single base value would put one of them off its rung. Base UI's `Tabs.Tab` sets `focusableWhenDisabled`,
  // so a disabled tab stays keyboard-focusable and never carries the native `disabled` attribute
  // — only `aria-disabled` — which is why the disabled styling below keys off `aria-disabled:`,
  // not the `disabled:` pseudo-class (that would never match). Deliberately NOT
  // `aria-disabled:pointer-events-none` (the `control-chrome` pattern): that would make
  // `cursor-not-allowed` a dead class (the browser skips a `pointer-events:none` element during
  // cursor hit-testing and falls back to an ancestor that declares no cursor of its own here) and
  // would break the whole point of `focusableWhenDisabled` — staying hoverable/click-focusable so
  // a future tooltip can explain why the tab is disabled. The `hover:`/`active:` utilities below
  // are guarded with `not-aria-disabled:` instead, so only the wash is suppressed.
  //
  // Two things that guard MUST get right, both pinned by `DisabledCanary`:
  //   1. Negate the aria-disabled VALUE, never its presence. Base UI writes `aria-disabled` on
  //      every tab — `"false"` on the enabled ones — so a `:not([aria-disabled])` presence check
  //      matches nothing and silently deletes the wash. `not-aria-disabled:` compiles to
  //      `:not([aria-disabled="true"])`, which is the correct form.
  //   2. Exclude the selected tab (`not-data-active:`). `:not([aria-disabled="true"]):hover` is a
  //      (0,3,0) selector and `[data-active]` only (0,2,0), so an unguarded wash outranks the
  //      selected tab's own chrome and strips its raised card the moment a pointer touches it.
  //
  // The focus ring is declared per `variant`, not here: `contained` rings its own rounded button,
  // but the `underline` button is a square-cornered column (label + bar track) sitting flush with
  // the top of the list's scroll viewport, so a ring on it draws square corners around the bar and
  // gets its top/bottom edges clipped. That variant hands the ring to `TabUnderlineLabel` instead
  // (see `tabUnderlineLabelVariants`) and only keeps `outline-none` here.
  "cursor-pointer whitespace-nowrap transition-colors outline-none select-none aria-disabled:cursor-not-allowed aria-disabled:text-disabled",
  {
    variants: {
      variant: {
        // Hover/pressed darken the background only — the label stays `text-secondary` until the
        // tab is actually selected, where `data-active` jumps it to `text-primary`.
        contained:
          "inline-flex h-6 items-center justify-center gap-1 rounded-md border-sm border-transparent px-1.5 text-body-xs-medium text-secondary [--node-size:var(--control-glyph-sm)] not-aria-disabled:not-data-active:hover:bg-layer-transparent-hover focus-visible:ring-2 focus-visible:ring-accent-strong not-aria-disabled:not-data-active:active:bg-layer-transparent-active data-active:border-subtle-1 data-active:bg-layer-2 data-active:text-primary data-active:shadow-raised-200",
        // Height pins the ladder's `md` (28px label box via `h-7` on `TabUnderlineLabel`). Type is
        // deliberately off-ladder: `body-sm` (14px) instead of md's `body-xs` (13px) — one rung
        // louder — so the flatter underline chrome stays scannable on full-width content areas.
        // Documented in `apps/docs/src/lib/sizing-tokens.ts` (Tabs family notes); do not "fix"
        // this back to 13px without updating that row.
        underline:
          "group/tab inline-flex flex-col items-stretch gap-2 text-body-sm-medium [--node-size:var(--control-glyph-md)]",
      },
      // `flex-1` (`flex: 1 1 0%`) splits the row into equal-width tabs when the enclosing
      // `TabsList` is `stretch: full` — each variant's own base classes already own their internal
      // alignment. Once a label's natural width exceeds its equal share, `whitespace-nowrap` plus
      // the default `min-width: auto` stops that tab from shrinking further, so it grows past its
      // share and the row falls back to horizontal scrolling, same as `auto` (see
      // `OverflowScrollsFullWidth`).
      stretch: {
        auto: "",
        full: "flex-1",
      },
    },
    // No `defaultVariants` — see `tabsListVariants` above; `stretch` only ever arrives via
    // `TabsStretchContext`.
  },
);

export type TabVariantProps = StrictVariantProps<typeof tabVariants>;

// The label owns the underline tab's visible text color, so the disabled variant has to key off the
// parent tab's `aria-disabled` here (not `disabled` — see the note on `tabVariants` above; the tab
// button's own `aria-disabled:text-disabled` can't reach text a child colors explicitly). The
// parent tab keeps real `:hover`/`:active` (no `pointer-events-none` — see `tabVariants`), so the
// hover/press wash below is guarded with a hand-written `group-[&:hover:not(...)]/tab:` compound
// selector rather than `group-hover/tab:`, since Tailwind's `not-*` negates the CURRENT element's
// own state, not a named group's. The compound spells out both guards `not-aria-disabled:` and
// `not-data-active:` give the contained tab for free — the `="true"` comparison (never a bare
// presence check, which matches the enabled tab's own `aria-disabled="false"`) and the selected-tab
// exclusion. See the numbered note on `tabVariants`; `DisabledCanary` pins both.
//
// The keyboard focus ring lives here too, keyed off the parent button's `:focus-visible` through
// `group-focus-visible/tab:` (the label itself is never focused). It is `ring-inset` because the
// label sits flush with the top of the list's scroll viewport (the list has horizontal padding
// only), so an outside ring would lose its top edge to overflow clipping; the label's own
// `px-2 py-0.5` keeps the 2px inset ring clear of the text. Matches the GitHub underline-nav
// treatment: a rounded ring around the label pill, with the bar left outside it.
export const tabUnderlineLabelVariants = cva(
  "flex h-7 items-center justify-center gap-1.5 rounded-md px-2 py-0.5 text-tertiary transition-colors group-focus-visible/tab:ring-2 group-focus-visible/tab:ring-accent-strong group-focus-visible/tab:ring-inset group-aria-disabled/tab:bg-transparent group-aria-disabled/tab:text-disabled group-data-active/tab:bg-layer-transparent-selected group-data-active/tab:text-primary group-[&:active:not([aria-disabled='true']):not([data-active])]/tab:bg-layer-transparent-active group-[&:active:not([aria-disabled='true']):not([data-active])]/tab:text-primary group-[&:hover:not([aria-disabled='true']):not([data-active])]/tab:bg-layer-transparent-hover group-[&:hover:not([aria-disabled='true']):not([data-active])]/tab:text-secondary",
);

export const tabUnderlineBarTrackVariants = cva("flex px-2");

export const tabUnderlineBarVariants = cva(
  // Same compound guard as `tabUnderlineLabelVariants` — see that comment for why
  // `group-hover/tab:`/`group-active/tab:` alone would wash a disabled tab, and why the
  // aria-disabled test compares the value rather than checking the attribute's presence.
  "h-[3px] w-full rounded-full bg-current text-transparent transition-colors group-data-active/tab:text-transparent group-[&:active:not([aria-disabled='true']):not([data-active])]/tab:text-icon-tertiary group-[&:hover:not([aria-disabled='true']):not([data-active])]/tab:text-icon-placeholder",
);

// `w-full` fills the root's content box. `min-w-0` zeros the flex item's automatic minimum width
// (the cross axis of the column root) so long unbreakable panel content can shrink/wrap inside
// the parent instead of forcing the root's min-content wider than `w-full` resolved to.
export const tabsPanelVariants = cva(
  "w-full min-w-0 text-body-sm-regular text-secondary outline-none",
  {
    variants: {
      layout: {
        content: "",
        fill: "min-h-0 flex-1",
      },
    },
  },
);

type TabsPanelVariantConfig = VariantProps<typeof tabsPanelVariants>;
export type TabsPanelLayout = NonNullable<TabsPanelVariantConfig["layout"]>;
export type TabsPanelVariantProps = StrictVariantProps<typeof tabsPanelVariants>;

export const tabsIndicatorVariants = cva(
  cx(
    "absolute top-[calc(var(--active-tab-top)+1.75rem+0.5rem)] left-[calc(var(--active-tab-left)+0.5rem)] h-[3px] w-[calc(var(--active-tab-width)-1rem)]",
    "rounded-full bg-inverse transition-all duration-150",
  ),
);
