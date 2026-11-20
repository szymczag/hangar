import { cva, cx } from "class-variance-authority";

import { controlSize } from "../../internal/control-group";
import { type StrictVariantProps } from "../../internal/variant-props";

// Stacks the trigger and the row on top of each other (both children pinned to grid cell 1/1)
// instead of letting them flow as separate boxes: with `hidden` gone, neither one collapses to zero
// layout footprint anymore (that's now the trigger/row's own job, via their individual width
// tracks below), so without this they'd render as two sequential blocks instead of one thing
// growing in place. The container's own size then just follows whichever child currently has
// nonzero width — no width animation of its own needed here. Parent layout owns the outer width
// (e.g. a toolbar slot or `w-*` wrapper); expand/collapse morphs the inner tracks inside that box.
export const expandableSearchTrackVariants = cva("grid [&>*]:col-start-1 [&>*]:row-start-1");

// Both this and `expandableSearchRowVariants` are a CSS-grid `minmax(0,0fr)`/`minmax(0,1fr)` track:
// the one (Tailwind-expressible) way to animate width to/from an element's own intrinsic size — a
// plain `width` transition can't target `auto`. A bare `0fr`/`1fr` track keeps an implicit
// `minmax(auto,…)` floor (the item's own min-content size), so it never actually reaches 0 — the
// explicit `minmax(0,…)` overrides that floor. `[&>*]:min-w-0` additionally lets the grid ITEM
// compress below its intrinsic width instead of forcing the track wide; `overflow-hidden` clips it
// as the track shrinks. `motion-safe:` (Tailwind's `prefers-reduced-motion: no-preference` variant)
// carries only the `transition`/`duration`/`easing` — the base (unprefixed) classes are the
// resting/toggled STATE, so a reduced-motion user gets today's instant snap for free, not a
// fallback path.
//
// Centers the collapsed trigger's own (smaller) `IconButton` square inside a box matching the
// expanded `AutocompleteInputGroup` row's height at the same size step (`controlSize`, the same
// shared scale Autocomplete's own row already uses) — otherwise collapsing/expanding shifts height
// by a constant 8px at every size (IconButton's own box scale runs 20/24/28/32, Autocomplete's row
// scale runs 28/32/36/40).
export const expandableSearchTriggerVariants = cva(
  cx(
    "grid place-items-center [&>*]:min-w-0",
    // `overflow-hidden` only while actually shrinking away (`data-expanded`) — at rest (this
    // trigger's own natural size), it stays `visible` so the button's own focus ring isn't
    // clipped flat by a same-size overflow-hidden box (a ring extends past the border-box on
    // purpose; `overflow-hidden` doesn't know that and slices it off square at the edge).
    "overflow-visible data-expanded:overflow-hidden",
    "grid-cols-[minmax(0,1fr)] opacity-100 data-expanded:grid-cols-[minmax(0,0fr)] data-expanded:opacity-0",
    "motion-safe:transition-[grid-template-columns,opacity] motion-safe:duration-200 motion-safe:ease-out",
  ),
  {
    variants: {
      size: {
        md: controlSize.md,
        lg: controlSize.lg,
        xl: controlSize.xl,
        "2xl": controlSize["2xl"],
      },
    },
  },
);

// No separate exported per-axis size type here (rule 9's usual pattern): `size` is never chosen
// independently — it's always fed the same `AutocompleteSize` value the enclosing `ExpandableSearch`
// received, so a standalone `ExpandableSearchTriggerSize` would just duplicate that type.
export type ExpandableSearchTriggerVariantProps = StrictVariantProps<
  typeof expandableSearchTriggerVariants
>;

// The expanded row's own track — exact inverse polarity of the trigger's, driven by the same
// `data-expanded` boolean, so one shrinks as the other grows. No `size` axis: `AutocompleteInputGroup`
// already sizes itself; this wrapper only owns the width/opacity animation.
export const expandableSearchRowVariants = cva(
  cx(
    "grid [&>*]:min-w-0",
    // Same reasoning as the trigger's, inverse polarity: `overflow-hidden` only while collapsed
    // (there's no focus ring to protect when nothing inside is visible or focusable), `visible`
    // once expanded so `AutocompleteInputGroup`'s own focus ring renders its full rounded curve
    // instead of getting clipped flat at the corners.
    "overflow-hidden data-expanded:overflow-visible",
    "grid-cols-[minmax(0,0fr)] opacity-0 data-expanded:grid-cols-[minmax(0,1fr)] data-expanded:opacity-100",
    "motion-safe:transition-[grid-template-columns,opacity] motion-safe:duration-200 motion-safe:ease-out",
  ),
);
