import * as React from "react";

import { DROPDOWN_EDGE_GAP_PX } from "../../internal/dropdown-edge-gap";
import { MENU_FIT_FLOOR_PX, resolveFitSide, type FitSide } from "../../internal/fit-side";
import { MenuContentSurface, type MenuSurfaceProps } from "./menu-content.shared";
import { MenuTriggerElementContext } from "./menu-context";

export type { MenuContentSizing } from "./menu-content.shared";

export type MenuContentProps = Omit<
  MenuSurfaceProps,
  "side" | "sideOffset" | "collisionPadding" | "sizing"
> & {
  /** Which side of the trigger the menu opens toward. @default "bottom" */
  side?: MenuSurfaceProps["side"];
  /** Distance in px between the trigger and the menu. @default 6 */
  sideOffset?: MenuSurfaceProps["sideOffset"];
  /**
   * Minimum gap in px between the menu and the viewport edge it would otherwise touch.
   *
   * @default 16
   */
  collisionPadding?: MenuSurfaceProps["collisionPadding"];
  /**
   * How the menu popup takes its width. `auto` is the content's width — never narrower than 204px,
   * never wider than 400px or the room beside the trigger, and held while open so a list that
   * filters down does not reflow. `anchor` matches the trigger's width instead, growing only with
   * its content. The default applies to an omitted _and_ an explicitly `undefined` value.
   *
   * @default "auto"
   */
  sizing?: MenuSurfaceProps["sizing"];
  /**
   * What decides which side of the trigger the menu opens on when space is short. `fit`, the
   * default, shrinks before flipping: the menu keeps `side` while the usable space there clears a
   * 178px floor (six rows plus the panel's chrome), and flips only when it does not and the other
   * side does; when neither clears the floor, the bigger side wins. The side is resolved each time
   * the menu opens and holds while it stays open. `flip` is Base UI's behavior: jump to the other
   * side whenever the menu's full height does not fit and the other side has more room — even when
   * this side held a usable menu. `fit` applies to a vertical `side`, needs the menu's own
   * `MenuTrigger` to measure against (a menu opened without one falls back to `flip`), and defers
   * to an explicit `collisionAvoidance`.
   *
   * @default "fit"
   */
  heightBehavior?: "flip" | "fit";
};

/** Numeric top/bottom the fit measurement can use, from the looser Base UI prop types. */
function verticalPadding(padding: MenuSurfaceProps["collisionPadding"]): {
  top: number;
  bottom: number;
} {
  if (typeof padding === "number") return { top: padding, bottom: padding };
  if (padding && typeof padding === "object") {
    return { top: padding.top ?? 0, bottom: padding.bottom ?? 0 };
  }
  return { top: 5, bottom: 5 }; // Base UI's own default
}

/** The boundary's vertical extent: an element's rect, a given rect, or the visual viewport. */
function boundaryExtent(boundary: MenuSurfaceProps["collisionBoundary"]): {
  top: number;
  bottom: number;
} {
  const first = Array.isArray(boundary) ? boundary[0] : boundary;
  if (first instanceof Element) {
    const rect = first.getBoundingClientRect();
    return { top: rect.top, bottom: rect.bottom };
  }
  if (first && typeof first === "object" && "y" in first && "height" in first) {
    return { top: first.y, bottom: first.y + first.height };
  }
  const viewport = window.visualViewport;
  return viewport
    ? { top: viewport.offsetTop, bottom: viewport.offsetTop + viewport.height }
    : { top: 0, bottom: window.innerHeight };
}

/**
 * The menu surface: Base UI's portal and positioner wrapped around an elevated, scrollable panel
 * holding the `role="menu"` popup. Optional `search` and `footer` chrome stays pinned outside the
 * scroll area. Rows (`MenuItem`, `MenuGroup`, `MenuSeparator`, …) are its children.
 */
export function MenuContent({
  side = "bottom",
  sideOffset = 6,
  align = "start",
  collisionPadding = DROPDOWN_EDGE_GAP_PX,
  sizing = "auto",
  heightBehavior = "fit",
  collisionBoundary,
  collisionAvoidance,
  ...props
}: MenuContentProps) {
  const triggerElement = React.useContext(MenuTriggerElementContext);
  const fitting = heightBehavior === "fit" && (side === "bottom" || side === "top");
  const preferred: FitSide = side === "top" ? "top" : "bottom";
  const [fitSide, setFitSide] = React.useState<FitSide>(preferred);
  // `fit` may only pin the positioner (`side: "none"`) once it has a trigger to measure against.
  // A menu opened without propel's `MenuTrigger` — a menubar trigger, a handle with detached
  // launch points — records nothing, and pinning without measuring would reintroduce the very
  // no-floor shrink `fit` exists to prevent. Those menus fall back to `flip` behavior instead.
  const [hasTrigger, setHasTrigger] = React.useState(false);

  // Resolve the side each time the menu opens, before the positioner runs. The open signal is the
  // trigger's own `aria-expanded`: Base UI sets it for every open path (pointer, keyboard,
  // controlled), and the MutationObserver microtask re-renders us before the browser paints, so a
  // side change never flashes. `MenuContent` itself stays mounted across open/close — only the
  // portal's children unmount — which is why mount alone is not the signal.
  React.useLayoutEffect(() => {
    if (!fitting) return undefined;
    const trigger = triggerElement?.current;
    setHasTrigger(trigger != null);
    if (!trigger) return undefined;

    const resolve = () => {
      const rect = trigger.getBoundingClientRect();
      const padding = verticalPadding(collisionPadding);
      const offset = typeof sideOffset === "number" ? sideOffset : 6;
      const extent = boundaryExtent(collisionBoundary);
      setFitSide(
        resolveFitSide({
          trigger: { top: rect.top, bottom: rect.bottom },
          boundary: extent,
          preferred,
          sideOffset: offset,
          // One gutter per decision: feed the floor the larger per-side padding so the
          // comparison never flatters a side its own gutter would then eat.
          collisionPadding: Math.max(padding.top, padding.bottom),
          floor: MENU_FIT_FLOOR_PX,
        }),
      );
    };

    const sync = () => {
      if (trigger.getAttribute("aria-expanded") === "true") resolve();
    };
    sync(); // covers defaultOpen and a re-render arriving while already open
    const observer = new MutationObserver(sync);
    observer.observe(trigger, { attributes: true, attributeFilter: ["aria-expanded"] });
    return () => observer.disconnect();
  }, [fitting, triggerElement, preferred, sideOffset, collisionPadding, collisionBoundary]);

  const fitActive = fitting && hasTrigger;

  return (
    <MenuContentSurface
      side={fitActive ? fitSide : side}
      sideOffset={sideOffset}
      align={align}
      collisionPadding={collisionPadding}
      collisionBoundary={collisionBoundary}
      // `fit` owns the side decision, so the positioner must not re-flip it; an explicit
      // consumer-passed avoidance still wins.
      collisionAvoidance={
        collisionAvoidance ?? (fitActive ? { side: "none", align: "shift" } : undefined)
      }
      sizing={sizing}
      {...props}
    />
  );
}
