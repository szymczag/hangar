import { ScrollArea as BaseScrollArea } from "@base-ui/react/scroll-area";
import * as React from "react";

import {
  ScrollArea as ScrollAreaElement,
  ScrollAreaCorner,
  type ScrollAreaOrientation,
  ScrollAreaScrollbar,
  type ScrollAreaScrollbarVisibility,
  type ScrollAreaSize,
  ScrollAreaThumb,
  type ScrollAreaVariant,
  ScrollAreaViewport,
} from "../../elements/scroll-area";

export type {
  ScrollAreaOrientation,
  ScrollAreaScrollbarSize,
  ScrollAreaScrollbarVisibility,
  ScrollAreaSize,
  ScrollAreaVariant,
} from "../../elements/scroll-area";

// propel's scroll container, built on Base UI ScrollArea. Unlike a re-skinned native
// scrollbar it paints a real DOM thumb, so it renders consistently across browsers
// (including Firefox and touch), insets the thumb from the edge, and reveals only on
// interaction. The thumb uses propel's `--scrollbar-thumb*` tokens: shown while the
// area is hovered or scrolling, darker on thumb hover, darkest while dragging, over a
// transparent track (specs + in-product example). It fills its parent (a flex column or
// any parent with a definite height), so constrain the parent's height (or width) to make
// the content scroll. Reveal/width are driven by the `visibility` and `size` props threaded
// to each `ScrollAreaScrollbar`; `variant` decides whether the track overlays the content
// or reserves its own lane. Base UI Root props
// (minus className/style/render) forward onto the root for ids, aria, overflow thresholds, etc.
//
// Base UI's optional `ScrollArea.Content` wrapper is intentionally omitted: Figma has no
// Content part, Content is unstyled in typical use, and children sit directly in the Viewport
// (composers who need Content can graft Base UI themselves).

export type ScrollAreaProps = Omit<
  BaseScrollArea.Root.Props,
  "className" | "style" | "render" | "children"
> & {
  /**
   * Which axes scroll (required, no silent default). `vertical`/`horizontal` render a single
   * scrollbar; `both` renders both plus the corner. Render only the axes the content can actually
   * overflow so an unused scrollbar never reserves space or reveals.
   */
  orientation: ScrollAreaOrientation;
  /**
   * How the scrollbar sits against the content. `overlay` floats it over the content's edge.
   * `inset` always reserves its track (for each rendered axis), so the thumb never covers content
   * and content never shifts when it starts or stops overflowing.
   *
   * @default "overlay"
   */
  variant?: ScrollAreaVariant;
  /**
   * When the scrollbar is shown. `auto` hides it at rest and reveals it on hover/scroll (fades when
   * idle). `always` keeps it permanently visible.
   *
   * @default "auto"
   */
  visibility?: ScrollAreaScrollbarVisibility;
  /**
   * Scrollbar gutter size (propel scrollbar scale). Stable full gutter; pad matches native
   * `scrollbar-*`: `sm` — 8 px / 2 → 4 px thumb; `md` — 10 / 2 → 6; `lg` — 12 / 2 → 8.
   *
   * @default "md"
   */
  size?: ScrollAreaSize;
  /** Ref to the scrolling viewport, for scroll restoration or virtualized collections. */
  viewportRef?: React.Ref<HTMLDivElement>;
  /** The scrollable content (rendered inside the viewport). */
  children: React.ReactNode;
};

/**
 * A scroll container with propel's scrollbar, built on Base UI `ScrollArea`. Use it to wrap any
 * overflowing content (menus, panels, long lists). It fills its parent: inside a flex column it
 * grows to fill the column (`flex-1`), and inside any other parent with a definite height it takes
 * that height (`h-full`). Constrain the parent's height (or width), and the viewport scrolls when
 * the content overflows. `variant` picks whether the scrollbar overlays the content or keeps its
 * own lane.
 */
export function ScrollArea({
  orientation,
  variant = "overlay",
  visibility = "auto",
  size = "md",
  viewportRef,
  children,
  ...props
}: ScrollAreaProps) {
  const showVertical = orientation !== "horizontal";
  const showHorizontal = orientation !== "vertical";
  return (
    // The Root sizes itself two ways: as a flex item it grows to fill a flex column
    // (`flex-1 min-h-0`), and in any other parent with a definite height it takes that height
    // (`h-full`; in a flex column `flex-basis` wins, and against an indefinite height the
    // percentage falls back to auto, so a `max-h` parent still hugs short content). It lays its
    // viewport out as a flex column; the Viewport is a `flex-1` child whose `overflow: scroll`
    // (set by Base UI) gives it an automatic min-height of 0, so it bounds to the root and
    // scrolls. The scrollbars are positioned absolutely by Base UI, so they never take flex
    // space. The Base UI behavior parts graft onto the styled `elements` parts via `render`.
    <BaseScrollArea.Root
      {...props}
      render={<ScrollAreaElement variant={variant} size={size} orientation={orientation} />}
    >
      <BaseScrollArea.Viewport
        ref={viewportRef}
        render={<ScrollAreaViewport orientation={orientation} />}
      >
        {children}
      </BaseScrollArea.Viewport>
      {showVertical ? (
        <BaseScrollArea.Scrollbar
          orientation="vertical"
          render={<ScrollAreaScrollbar visibility={visibility} size={size} />}
        >
          <BaseScrollArea.Thumb render={<ScrollAreaThumb />} />
        </BaseScrollArea.Scrollbar>
      ) : null}
      {showHorizontal ? (
        <BaseScrollArea.Scrollbar
          orientation="horizontal"
          render={<ScrollAreaScrollbar visibility={visibility} size={size} />}
        >
          <BaseScrollArea.Thumb render={<ScrollAreaThumb />} />
        </BaseScrollArea.Scrollbar>
      ) : null}
      {orientation === "both" ? <BaseScrollArea.Corner render={<ScrollAreaCorner />} /> : null}
    </BaseScrollArea.Root>
  );
}
