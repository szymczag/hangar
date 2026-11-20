import { cva, cx, type VariantProps } from "class-variance-authority";

import { listItemPrimaryVariants } from "../../internal/list-item-primary";
import { type StrictVariantProps } from "../../internal/variant-props";

/** The list container — a vertical stack of rows. Role/aria are supplied by the consumer. */
const listDefaultVariants = { gap: "0.5" } as const;

export const listVariants = cva("flex w-full flex-col", {
  variants: {
    gap: {
      px: "gap-px",
      "0.5": "gap-0.5",
    },
  },
  defaultVariants: listDefaultVariants,
});
type ListVariantConfig = VariantProps<typeof listVariants>;
export type ListGap = NonNullable<ListVariantConfig["gap"]>;
export type ListVariantProps = StrictVariantProps<
  typeof listVariants,
  keyof typeof listDefaultVariants
>;

/**
 * A row wrapper. It owns the chrome (hover + selected fill + focus ring) and the layout, but is not
 * itself the focusable target — that's the `ListItemLink`/`ListItemButton` it wraps. Selected and
 * focus are read off descendants via `:has`, so the whole row reacts to its primary's state. The
 * full-row ring keys off the primary only (`[data-list-item-primary]:focus-visible`) — sibling
 * controls (disclosure, menus, etc.) keep their own focus chrome instead of lighting the whole
 * row.
 *
 * Height is fixed at 32px (`h-8`, the ladder's `lg` step) for both density values — Figma's Nav
 * item keeps a single row height and only ramps type. That is intentional off-ladder reuse of
 * `comfortable`/`compact` (text density, not control height); see `size-scale.ts`.
 */
const listItemDefaultVariants = { level: 1, density: "comfortable" } as const;

export const listItemVariants = cva(
  cx(
    // 32px row = the ladder's `lg` rung, so its glyph slot is `--control-glyph-lg`. Declared here
    // rather than left to the caller: the property does not fall back, so a row that set nothing
    // made every call site pin `<Icon size="md">` by hand to avoid the svg's intrinsic 24px.
    "group/list-item relative flex h-8 w-full items-center gap-2 rounded-lg pr-2 [--node-size:var(--control-glyph-lg)]",
    "text-secondary transition-colors",
    "hover:bg-layer-transparent-hover",
    "active:bg-layer-transparent-active",
    "has-[[aria-current=page]]:bg-layer-transparent-selected has-[[aria-current=page]]:text-primary",
    "has-[[data-list-item-primary]:focus-visible]:ring-2 has-[[data-list-item-primary]:focus-visible]:ring-accent-strong",
  ),
  {
    variants: {
      // Nesting depth — steps the row's left inset by spacing/2 (8px) per level.
      level: {
        1: "pl-2",
        2: "pl-4",
        3: "pl-6",
        4: "pl-8",
        5: "pl-10",
      },
      // Label/counter text density only — row stays h-8 and icons stay 16px; type scale drops
      // (14px → 13px). Named `density` (not `size`) so ladder `md`/`lg` labels are never reused
      // at the wrong height.
      density: {
        comfortable: "text-body-sm-medium",
        compact: "text-body-xs-medium",
      },
    },
    compoundVariants: [
      // Pressed only darkens the label at `comfortable` — `compact` pressed text stays secondary.
      { density: "comfortable", class: "active:text-primary" },
    ],
    defaultVariants: listItemDefaultVariants,
  },
);
type ListItemVariantConfig = VariantProps<typeof listItemVariants>;
export type ListItemLevel = NonNullable<ListItemVariantConfig["level"]>;
export type ListItemDensity = NonNullable<ListItemVariantConfig["density"]>;
export type ListItemVariantProps = StrictVariantProps<
  typeof listItemVariants,
  keyof typeof listItemDefaultVariants
>;

// A row's primary — `ListItemLink` (`<a>`) and `ListItemButton` (`<button>`) — wears the shared
// row-primary chrome from `internal/list-item-primary` (rule 4); they differ only in the element
// they render (rule 6c).
export const listItemLinkVariants = listItemPrimaryVariants;
export type ListItemLinkVariantProps = StrictVariantProps<typeof listItemLinkVariants>;

export const listItemButtonVariants = listItemPrimaryVariants;
export type ListItemButtonVariantProps = StrictVariantProps<typeof listItemButtonVariants>;

/** The row label — fills the remaining width and truncates. */
export const listItemLabelVariants = cva("min-w-0 flex-1 truncate");
export type ListItemLabelVariantProps = StrictVariantProps<typeof listItemLabelVariants>;

/**
 * The row's trailing count chip (e.g. an unread count). Figma's fill is a raw 10% black overlay —
 * not theme-aware and unreadable in dark mode (measured: text and background land within ~0.02
 * lightness of each other). Uses `Badge`'s `neutral` palette (`bg-layer-3`/`text-label-grey-text`)
 * instead, which is already proven correct in both themes; the exact shade drifts slightly from the
 * literal Figma value, which didn't match any existing token anyway.
 *
 * Inherits `ListItem`'s `density` font-size/weight (`text-body-sm-medium` / `text-body-xs-medium`)
 * so label and counter share density, but pins `leading-none` — body utilities ship `line-height:
 * 1.54`, which stretches the chip into a tall pill. Color stays pinned (`text-label-grey-text`) so
 * the chip doesn't follow selected/pressed row text.
 */
export const listItemCounterVariants = cva(
  "flex shrink-0 items-center justify-center rounded-sm bg-layer-3 px-0.5 leading-none text-label-grey-text",
);
export type ListItemCounterVariantProps = StrictVariantProps<typeof listItemCounterVariants>;

/**
 * The row's trailing expand/collapse control — a sibling of the row's primary
 * (`ListItemLink`/`ListItemButton`), never nested inside it (a button inside a link/button is
 * invalid). Geometry: 20px box, 24px effective touch target via the transparent `before:-inset-0.5`
 * ring, 14px node — close to (but not the same as) `IconButton` `sm` (24px box / 16px glyph); kept
 * local until a third caller hits the rule-of-3. Carries `group` so the composed
 * `DisclosureIndicator` rotates off it. No own hover/active fill — it's a descendant of `ListItem`,
 * which already fills on hover/active for any interactive child. It DOES carry its own
 * focus-visible ring on the 20px box: the row's full-row ring only fires for the primary
 * (`[data-list-item-primary]`, see `listItemVariants`), so sibling controls stay visually distinct.
 * Disabled mirrors `listSectionTriggerVariants` (`disabled` / `data-disabled` cursor).
 */
export const listItemDisclosureTriggerVariants = cva(
  "group relative flex size-5 shrink-0 cursor-pointer items-center justify-center rounded-sm outline-none [--node-size:var(--control-glyph-xs)] before:absolute before:-inset-0.5 before:content-[''] focus-visible:ring-2 focus-visible:ring-accent-strong disabled:cursor-not-allowed data-disabled:cursor-not-allowed",
);
export type ListItemDisclosureTriggerVariantProps = StrictVariantProps<
  typeof listItemDisclosureTriggerVariants
>;

/**
 * A static section heading — a small, muted label that names a group of rows. The non-interactive
 * sibling of `listSectionTrigger`: no button affordance (no hover/focus/cursor), it just titles a
 * static section in a settings-style sidebar.
 */
export const listSectionHeadingVariants = cva(
  cx("flex h-7 w-full items-center px-2 py-1", "text-body-xs-semibold text-tertiary"),
);
export type ListSectionHeadingVariantProps = StrictVariantProps<typeof listSectionHeadingVariants>;

/**
 * The vertical gap between a `ListSection` heading and its first row. `ListSection` mounts rows
 * directly in the Collapsible panel (not `CollapsiblePanelContent` — that carries horizontal inset
 * + prose that would double-pad rows and mis-style list text), so this is the only source of that
 * spacing.
 */
export const listSectionPanelContentVariants = cva("pt-2");
export type ListSectionPanelContentVariantProps = StrictVariantProps<
  typeof listSectionPanelContentVariants
>;

/**
 * A collapsible section's header — a small, muted heading that toggles the section, with the
 * chevron pushed to the inline-end edge of the row. Styled `ListSectionTrigger` (grafted as
 * `BaseCollapsible.Trigger`'s render target); carries the `group` so a `DisclosureIndicator` inside
 * rotates off its `data-panel-open`.
 */
export const listSectionTriggerVariants = cva(
  cx(
    "group flex w-full items-center justify-between gap-1 rounded-md px-2 py-1 [--node-size:var(--control-glyph-md)]",
    // Same type as `listSectionHeading` — the two are the same role (a muted label naming a
    // group of rows) and differ only in whether the section collapses, so a sidebar mixing
    // static and collapsible sections reads as one list.
    "text-body-xs-semibold text-tertiary transition-colors",
    "cursor-pointer outline-none hover:text-secondary",
    "focus-visible:ring-2 focus-visible:ring-accent-strong",
    "disabled:cursor-not-allowed data-disabled:cursor-not-allowed",
  ),
);
export type ListSectionTriggerVariantProps = StrictVariantProps<typeof listSectionTriggerVariants>;
