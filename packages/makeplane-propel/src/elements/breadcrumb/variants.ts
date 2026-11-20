import { cva, cx } from "class-variance-authority";

import { nodeSlotClass } from "../../internal/node-slot";

/**
 * Chrome for `BreadcrumbLink` — a navigable (hoverable) crumb anchor. Resting text is `tertiary`;
 * hover only adds the `transparent-hover` fill and does NOT recolor the text (the crumb goes
 * `primary` only when it is the current page — `BreadcrumbPage`). Icons render one step darker than
 * the text (`icon-secondary`), set on the icon slot, not inherited from `currentColor`.
 *
 * Fixed `h-6` (24px, per Figma): every crumb is the same height whether or not it has a leading
 * icon — the 16px icon and 13px text center inside the 24px box — so a mixed trail stays flush. The
 * leading-icon slot takes the `md` rung's glyph, so a consumer's `<Icon>` needs no `size`.
 */
export const breadcrumbLinkVariants = cva(
  "inline-flex h-6 cursor-pointer items-center gap-1.5 rounded-md px-1 text-body-xs-medium whitespace-nowrap text-tertiary transition-colors [--node-size:var(--control-glyph-md)] hover:bg-layer-transparent-hover",
);

/**
 * Chrome for `BreadcrumbPage` — the current page (non-interactive) crumb. Fixed `h-6` (24px); the
 * leading-icon slot takes the `md` rung's glyph via `--node-size`.
 */
export const breadcrumbPageVariants = cva(
  "inline-flex h-6 items-center gap-1.5 rounded-md px-1 text-body-xs-medium whitespace-nowrap text-primary [--node-size:var(--control-glyph-md)]",
);

/**
 * All-in-one chrome for a menu-trigger crumb: base pill styles, hover/open-state shifts, cursor,
 * and an optional `group/trigger` marker so descendant chevrons can react to the popup open state.
 */
export const breadcrumbTriggerVariants = cva(
  // Resting text `tertiary`; hover only adds the fill (no recolor, matching a link crumb). The
  // Current-page crumbs stay `primary`; an open ancestor menu also becomes `primary`.
  "inline-flex h-6 cursor-pointer items-center gap-1.5 rounded-md px-1 text-body-xs-medium whitespace-nowrap text-tertiary transition-colors [--node-size:var(--control-glyph-md)] hover:bg-layer-transparent-hover aria-[current=page]:text-primary data-popup-open:bg-layer-transparent-hover data-popup-open:text-primary",
  {
    variants: {
      /** Adds `group/trigger` so descendant elements can use `group-data-popup-open/trigger:*`. */
      group: {
        true: "group group/trigger",
        false: "",
      },
    },
  },
);

/**
 * The disclosure caret inside a menu crumb (`BreadcrumbMenuTrigger`). Pass a **chevron-down**
 * glyph: ancestor crumbs point inline-end while closed and rotate down while open. A current-page
 * crumb always points down (RTL-mirrored). Its own part — not the shared `DisclosureIndicator` —
 * because it carries a family-specific active state: resting `icon-secondary`, shifting to
 * `icon-primary` when the crumb's menu is open (`group-data-popup-open/trigger`), matching the
 * trigger text going `primary`. Takes the `sm` rung's glyph via `--node-size`, matching the
 * separator.
 */
export const breadcrumbTriggerIndicatorVariants = cva(
  cx(
    nodeSlotClass,
    // Carets and separators use the 14px glyph; leading icons use the 16px glyph.
    "text-icon-secondary transition duration-200 [--node-size:var(--control-glyph-sm)]",
    "-rotate-90 group-aria-[current=page]/trigger:rotate-0 group-data-popup-open/trigger:rotate-0",
    "rtl:rotate-90 rtl:group-aria-[current=page]/trigger:rotate-0 rtl:group-data-popup-open/trigger:rotate-0",
    "group-data-popup-open/trigger:text-icon-primary",
  ),
);

/** The `<li>` wrapper for every crumb (link, page, trigger). */
export const breadcrumbItemVariants = cva("inline-flex items-center");

/**
 * The visual divider between crumbs. Sizes any child icon to `--node-size` via the shared node-slot
 * class, so callers pass raw SVGs without extra wrappers. Chevron icons are RTL-mirrored via
 * `rtl:[&>svg]:-scale-x-100`. Fixed `size-6` (24px, per Figma): the chevron centers in a
 * 24px-square box so the divider matches the crumbs' height.
 */
export const breadcrumbSeparatorVariants = cva(
  cx(
    nodeSlotClass,
    "size-6 text-icon-secondary [--node-size:var(--control-glyph-sm)] rtl:[&>svg]:-scale-x-100",
  ),
);

/** The `<ol>` that carries the ordered trail of crumbs. */
export const breadcrumbListVariants = cva("flex items-center");
