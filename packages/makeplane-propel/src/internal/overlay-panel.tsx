import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";
import { cva, cx, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { ScrollArea } from "../components/scroll-area/index";
import { popupWidthRule, useHeldWidth } from "./popup-width";
import { surfaceVariants, type SurfaceVariantProps } from "./surface";

// The shared scrollable-overlay shell. Menu surfaces, the context-menu panel, the
// breadcrumb overflow menu and the toolbar picker all render
// the same thing: an elevated surface capped at the positioner's available height,
// whose body scrolls inside a `ScrollArea` while optional sticky chrome (a search
// header, a footer) stays pinned outside the scroll. This bundles that composition
// so each call site only supplies its positioner + a Base UI popup, and never
// re-derives the surface / max-height / overflow / scroll classes (they had drifted
// across call sites). It pairs with `internal/surface` (the card tokens) the same way.
//
// This is a component, but an internal one: it lives outside `components/` and
// `hooks/` (the only folders the build turns into published subpaths), so it is not
// part of the package's public API.
//
// Two ways families use it:
// - Wrapper (Menu, ContextMenu): the Base UI popup is `children`, so
//   menuitems stay direct children of `role="menu"` and header/footer sit outside
//   that popup (ARIA-valid).
// - Graft target (Combobox, Select): the Base UI popup renders *this* element. For Combobox,
//   Search then lives inside `role="dialog"`, so clicking a row does not leave the popup.
/**
 * The sizings that hold their width. The deprecated aliases render as `auto`, so they must BEHAVE
 * as `auto` too — gating on the literal `"auto"` gave them the styling without the hold, and a
 * filtering list under `sizing="menu"` shrank from 263px to the 192px floor while `sizing="auto"`
 * held at 263px.
 *
 * An omitted `sizing` is deliberately excluded: it means content width with no floor, no ceiling
 * and no hold, so it must keep reflowing.
 */
export const holdsWidth = (sizing: OverlayPanelSizing | undefined) =>
  sizing != null && sizing !== "anchor" && sizing !== "anchor-fixed";

const overlayPanelVariants = cva(
  cx(
    // Cap at the height the positioner measured, and lay the sticky header / scroll
    // body / sticky footer out as a clipped column.
    "flex max-h-(--available-height) flex-col overflow-hidden outline-none",
    // Open/close animation. `--transform-origin` is set on the Base UI positioner and
    // inherits down to here. Wrapper families (Menu, ContextMenu) never get
    // `data-starting-style` on this card — Base UI only sets it on the popup it
    // renders — so entry uses native `@starting-style` (`starting:`) and exit keys
    // off that nested popup via `has-[]`. Scope the `has-[]` to `role=menu` /
    // `role=dialog`: Combobox item indicators also get `data-ending-style` while a
    // row unchecks, and a bare `:has([data-ending-style])` would fade the whole card
    // as if it were closing. When this card *is* the popup (Combobox), those
    // attributes land here; `data-starting-style` / `data-ending-style` cover that
    // path without breaking the wrapper path.
    "origin-(--transform-origin) transition-[transform,opacity] duration-150 ease-out",
    "starting:scale-95 starting:opacity-0",
    "data-starting-style:scale-95 data-starting-style:opacity-0",
    "data-ending-style:scale-95 data-ending-style:opacity-0",
    "has-[[role=menu][data-ending-style]]:scale-95 has-[[role=menu][data-ending-style]]:opacity-0",
    "has-[[role=dialog][data-ending-style]]:scale-95 has-[[role=dialog][data-ending-style]]:opacity-0",
  ),
  {
    variants: {
      // `auto` is the content's width between the
      // floor and the ceiling (`internal/popup-width.ts`), held while open; `anchor` is the
      // trigger's width — never narrower than it, wider only with its content, capped by the room
      // beside the anchor rather than the ceiling, because a listbox must cover the field it
      // belongs to however wide that field is. `auto`/`anchor` use the base
      // `max-h-(--available-height)` so a long list grows to the viewport less the dropdown edge
      // gap (`internal/dropdown-edge-gap`), then scrolls. `anchor-fixed` is the exact anchor width
      // for windowed lists, capped at 288px (`18rem`) so a mid-open available-height settle cannot
      // shrink the popup under the virtualizer. Pair with `useAnimationFrameWithResizeObserver` so
      // short viewports (available height already under 288px) also avoid ResizeObserver re-entry.
      // `auto-fixed` is `auto`'s content width with the same 288px cap, for a windowed list whose
      // trigger is too narrow to set the popup's width (a pill).
      sizing: {
        auto: popupWidthRule,
        anchor: cx(
          "min-w-(--anchor-width)",
          "max-w-[max(var(--anchor-width),var(--available-width,100vw))]",
        ),
        "anchor-fixed":
          "max-h-[min(var(--available-height,100vh),18rem)] w-(--anchor-width) max-w-(--available-width)",
        "auto-fixed": cx(popupWidthRule, "max-h-[min(var(--available-height,100vh),18rem)]"),
        // The pre-0.4.0 names, kept so a consumer mid-migration compiles and renders unchanged. They
        // all map to `auto`, which is what replaced them; the old t-shirt sizes have no separate rule.
        // If any of `sm`/`md`/`lg` was meant to keep a distinct width cap, correct the mapping here —
        // it was inferred from the rewrite, not from their original definitions.
        /** @deprecated Use `auto`. */
        menu: popupWidthRule,
        /** @deprecated Use `auto`. */
        sm: popupWidthRule,
        /** @deprecated Use `auto`. */
        md: popupWidthRule,
        /** @deprecated Use `auto`. */
        lg: popupWidthRule,
      },
    },
  },
);

export type OverlayPanelSizing = NonNullable<VariantProps<typeof overlayPanelVariants>["sizing"]>;

/** The modes a new call site should use. The pre-0.4.0 names still compile but are deprecated. */
export type OverlayPanelSizingCurrent = Exclude<OverlayPanelSizing, "menu" | "sm" | "md" | "lg">;

export type OverlayPanelProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> & {
  /** Surface shadow depth (see `internal/surface`). */
  elevation: SurfaceVariantProps["elevation"];
  /** Surface corner radius (see `internal/surface`). */
  radius: SurfaceVariantProps["radius"];
  /**
   * How the panel takes its width. `auto` is the content's width, never narrower than 204px, never
   * wider than 400px or the room beside the anchor, and held while open so a filtering list does
   * not reflow. `anchor` matches the trigger's width and grows only with its content up to the room
   * beside the anchor. `anchor-fixed` is the exact anchor width for windowed lists, capped at 288px
   * so a mid-open height settle cannot shrink under the virtualizer (pair with
   * `useAnimationFrameWithResizeObserver` for short viewports). `auto-fixed` is `auto`'s width with
   * the same 288px cap, for a windowed list under a compact trigger. Omit for content width with no
   * floor, no ceiling and no hold. `auto` and `anchor` are as tall as the room the positioner
   * measured, then scroll.
   */
  sizing?: OverlayPanelSizing;
  /** Ref to the scroll body viewport, for a virtualizer or scroll restoration. */
  viewportRef?: React.Ref<HTMLDivElement>;
  /** Sticky content pinned above the scroll body (e.g. a `DropdownSearch`). */
  header?: React.ReactNode;
  /** Sticky content pinned below the scroll body (e.g. a `DropdownFooter`). */
  footer?: React.ReactNode;
};

export function OverlayPanel({
  render,
  elevation,
  radius,
  sizing,
  viewportRef,
  header,
  footer,
  children,
  ...props
}: OverlayPanelProps) {
  const holdRef = useHeldWidth(holdsWidth(sizing));
  const defaultProps: useRender.ElementProps<"div"> = {
    className: cx(surfaceVariants({ elevation, radius }), overlayPanelVariants({ sizing })),
    children: (
      <>
        {header}
        <ScrollArea orientation="vertical" viewportRef={viewportRef}>
          {children}
        </ScrollArea>
        {footer}
      </>
    ),
  };
  return useRender({
    defaultTagName: "div",
    render,
    ref: holdRef,
    props: mergeProps(defaultProps, props),
  });
}
