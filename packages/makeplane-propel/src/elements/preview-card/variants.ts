import { cva, cx } from "class-variance-authority";

// Preview Card wraps Base UI's parts; Base UI drives all open state through `data-*`
// attributes, so there are no styling axes (variant/size) to expose. The cva
// pairings below hold the static chrome for the styled parts that are UNIQUE to
// this family — Popup, Body, Image, Eyebrow, EyebrowLabel, Title, PropertyGroup,
// and Meta. The shared overlay description is adopted from `internal/` (rule 4a)
// and no longer lives here — Title is the one exception:
// it keeps its own recipe instead of the shared `internal/overlay-title` (see
// below). The eyebrow's leading slot is unstyled — no family-owned icon part, since a
// tint/size of the shared `internal/Icon` would only duplicate shared chrome (rule 6e).
// Figma's issue frame puts a 16×16 filled type indicator there; stories stand in with
// `Icon` at `tint="secondary" size="md"`.
//
// Body, Image, Eyebrow, EyebrowLabel, Title, PropertyGroup, and Meta are propel
// extensions with no Base UI counterpart; their styles encode the "always the
// same" items from the design spec — the text content area's layout + padding
// (Body), the image overflow/cover-fit (Image), the icon+text row (Eyebrow; an
// identifier via EyebrowLabel, or the heading via Title when there is no identifier),
// the card's primary heading (Title), the row of
// property chips (PropertyGroup), and the muted footer caption (Meta).

// The card surface. Padding lives on `PreviewCardBody` (per the spec, padding is
// "within the text content area") rather than here, so the popup is the bare
// surface: a `PreviewCardImage` clips itself (it carries its own overflow-hidden +
// rounding) and the body supplies its own padding. Unlike the shared `internal/popup-surface` chrome
// (`layer-1`/`border-subtle`/`shadow-overlay-100`, used by menu/dialog), the
// preview-card design spec binds `layer-2`/`border-subtle-1`/`shadow-overlay-200` —
// the same raised treatment `elements/tooltip` already uses standalone — so this
// family keeps its own surface cva rather than composing the shared one (rule 4a:
// divergent styling stays per-family). `w-74` (296px) is the spec's fixed card width
// across every anatomy (text/media/rich).
export const previewCardPopupVariants = cva(
  cx(
    "w-74 rounded-lg border-sm border-subtle-1 bg-layer-2 shadow-overlay-200 outline-none",
    "origin-(--transform-origin) transition-[opacity,transform] duration-150",
    "data-starting-style:scale-95 data-starting-style:opacity-0",
    "data-ending-style:scale-95 data-ending-style:opacity-0",
  ),
);

// Body: the text content area. Per the spec, the content layout (a column with the
// eyebrow above the title, description, property row, and meta caption) and the
// padding around it are "always the same", so they live here rather than in the
// consumer's composition. Padding is asymmetric per the spec (12px horizontal, 8px
// vertical), not a uniform `p-3`.
export const previewCardBodyVariants = cva("flex flex-col gap-1 px-3 py-2");

// Image: overflow-hidden + object-cover bake in the "always the same" thumbnail
// treatment from the design spec (clip + cover-fit). `w-full` makes the image full-bleed
// across the 296px card so callers don't pass `width={296}`. Only the top corners round
// (`rounded-t-lg`, matching the popup's own `rounded-lg`) so a full-bleed image sits
// flush against the card's top edge. Height is set by the consumer's layout.
export const previewCardImageVariants = cva("w-full overflow-hidden rounded-t-lg object-cover");

// Title: the card's primary heading. The design spec binds it to `text-body-sm-medium`
// (font-weight/medium) — a different, lighter weight than the shared
// `internal/overlay-title` "md" step (`text-body-sm-semibold`), which currently has no
// consumer (this family used to adopt it). Kept as its own recipe rather than forced
// through the shared primitive (rule 4a: divergent styling stays per-family).
// `min-w-0 truncate` keeps Figma's nowrap single line on the 296px card (and inside
// the eyebrow flex row) instead of wrapping and growing the card's height.
export const previewCardTitleVariants = cva("min-w-0 truncate text-body-sm-medium text-primary");

// Eyebrow: lays an optional leading node beside text on one row. Issue cards put a
// `PreviewCardEyebrowLabel` identifier (an issue key) here ABOVE a separate title;
// Figma's issue frame uses a 16×16 filled type indicator in the leading slot (stories
// stand in with `Icon`). Cycle / module / release / intake cards put `PreviewCardTitle`
// here and skip EyebrowLabel — those canvases have no muted identifier. The design no
// longer pairs the icon with the title itself (that was the old anatomy).
export const previewCardEyebrowVariants = cva("flex items-center gap-2");

// EyebrowLabel: the identifier text next to the eyebrow icon (an issue key, not the
// card's heading). Muted one step further than the description (`text-tertiary`, not
// `text-secondary`) and truncates to a single line instead of wrapping, per the spec.
// Not `text-disabled`: this is content a reader parses, and that token is exempt from
// contrast requirements because WCAG excuses inactive controls — it sat 0.04 above the
// AA line until the neutral-800 primitive was corrected, and then fell below it.
export const previewCardEyebrowLabelVariants = cva(
  "min-w-0 flex-1 truncate text-body-xs-regular text-tertiary",
);

// PropertyGroup: the row of property chips (status, priority, assignee, labels, …)
// a link-unfurl card shows beneath its description. A bare flex-wrap row — the
// chips themselves are the consumer's own components (`Pill`, `Avatar`,
// `Badge`, …), so this part supplies only the row layout, wrapping instead of
// overflowing when there are many.
export const previewCardPropertyGroupVariants = cva("flex flex-wrap items-center gap-2");

// Meta: the muted footer caption (a source domain, a relative timestamp, …) closing
// out the card's text content. Same muted caption treatment used elsewhere in the
// system (`text-caption-md-regular text-tertiary`), spelled out here rather than imported since
// `internal/menu-row-parts`'s `rowMetaClass` bakes in `shrink-0` for an inline
// trailing chip — this is a block-level line, not byte-identical (rule 4a).
export const previewCardMetaVariants = cva("text-caption-md-regular text-tertiary");
