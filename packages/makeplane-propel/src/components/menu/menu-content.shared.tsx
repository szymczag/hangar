import { Menu as BaseMenu } from "@base-ui/react/menu";
import * as React from "react";

import { MenuPopup } from "../../elements/menu";
import { DROPDOWN_EDGE_GAP_PX } from "../../internal/dropdown-edge-gap";
import { OverlayPanel, type OverlayPanelSizing } from "../../internal/overlay-panel";
import { Portal } from "../../internal/portal";
import { Positioner } from "../../internal/positioner";
import { MenuOpenContext, MenuSearchResetContext } from "./menu-context";

/** Menu surfaces are never windowed; keep the fixed-height sizings combobox-only. */
export type MenuContentSizing = Exclude<OverlayPanelSizing, "anchor-fixed" | "auto-fixed">;

/**
 * The props both menu surfaces share. `side`, `sideOffset`, `collisionPadding` and `sizing` carry
 * no `@default` here because the two surfaces pick different ones — `MenuContent` opens below its
 * trigger at 6px with an 8px viewport gutter, `MenuSubmenuContent` opens beside its parent row at
 * 4px and sets no gutter (both size themselves `auto`) — so each declares its own; otherwise the
 * generated props table would advertise one surface's default on both. `render` is omitted because
 * this surface always renders the styled `MenuPopup` as the popup's element, so a consumer-passed
 * one would be overwritten and silently do nothing.
 */
export type MenuSurfaceProps = Omit<BaseMenu.Popup.Props, "className" | "style" | "render"> & {
  /** Which side of the trigger the menu opens toward. */
  side?: BaseMenu.Positioner.Props["side"];
  /** Distance in px between the trigger and the menu. */
  sideOffset?: BaseMenu.Positioner.Props["sideOffset"];
  /** Alignment of the menu relative to the trigger along `side`. @default "start" */
  align?: BaseMenu.Positioner.Props["align"];
  /**
   * Additional offset in px along the align axis — slides the menu along the trigger's edge without
   * changing `align`.
   *
   * @default 0
   */
  alignOffset?: BaseMenu.Positioner.Props["alignOffset"];
  /** Minimum gap in px between the menu and the viewport edge it would otherwise touch. */
  collisionPadding?: BaseMenu.Positioner.Props["collisionPadding"];
  /**
   * The element or rect the menu is confined to when avoiding collisions. Base UI's clipping
   * ancestors when unset.
   */
  collisionBoundary?: BaseMenu.Positioner.Props["collisionBoundary"];
  /**
   * What to do when the menu would overflow the boundary, set per axis: flip to the other side,
   * shift along it, or stay put. Base UI flips the side and shifts the alignment when unset.
   */
  collisionAvoidance?: BaseMenu.Positioner.Props["collisionAvoidance"];
  /**
   * Keep the menu on screen after the trigger scrolls out of view, instead of following it out.
   *
   * @default false
   */
  sticky?: BaseMenu.Positioner.Props["sticky"];
  /**
   * Which CSS `position` the positioner uses. `fixed` escapes overflow-clipping ancestors, e.g. a
   * trigger inside a sticky header.
   *
   * @default "absolute"
   */
  positionMethod?: BaseMenu.Positioner.Props["positionMethod"];
  /**
   * Position against this element instead of the trigger — an element, a ref, a virtual element, or
   * a function returning one. Geometry only; the trigger keeps its role and interactions.
   */
  anchor?: BaseMenu.Positioner.Props["anchor"];
  /**
   * Stop tracking layout shifts of the anchor — position once, on open.
   *
   * @default false
   */
  disableAnchorTracking?: BaseMenu.Positioner.Props["disableAnchorTracking"];
  /**
   * How the menu popup takes its width. `auto` is the content's width — never narrower than 204px,
   * never wider than 400px or the room beside the trigger, and held while open so a list that
   * filters down does not reflow. `anchor` matches the trigger's width instead, growing only with
   * its content.
   */
  sizing?: MenuContentSizing;
  /**
   * A search field pinned above the `role="menu"` popup, e.g. a `MenuSearch`. The menu focuses it
   * when it opens, Escape closes from inside it, and ArrowDown/ArrowUp move focus into the list.
   */
  search?: React.ReactNode;
  /** Sticky chrome pinned below the `role="menu"` popup, e.g. a `MenuFooter`. */
  footer?: React.ReactNode;
};

export function MenuContentSurface({
  side,
  sideOffset,
  align,
  alignOffset,
  collisionPadding = DROPDOWN_EDGE_GAP_PX,
  collisionBoundary,
  collisionAvoidance,
  sticky,
  positionMethod,
  anchor,
  disableAnchorTracking,
  sizing,
  search,
  footer,
  children,
  ...props
}: MenuSurfaceProps & {
  side: BaseMenu.Positioner.Props["side"];
  sideOffset: BaseMenu.Positioner.Props["sideOffset"];
  align: BaseMenu.Positioner.Props["align"];
}) {
  // With a search field, focus belongs in it on open. The field stays OUTSIDE the `role="menu"`
  // popup (a menu's accessibility tree may not own a textbox), so Base UI's Tab guards never
  // reach it — but programmatic focus is not Tab, and the guards cannot bounce it. Base UI's own
  // initial focus lands on the popup element after mount, on its own schedule; racing it loses,
  // so this waits for that focus to arrive and redirects it to the field, once. A keyboard open
  // (ArrowDown on the trigger) focuses the first item instead of the popup — deliberate list
  // intent, so that focus spends the redirect without firing it, and nothing steals the row
  // afterward. `MenuSearch` owns the return trip (ArrowDown/Up).
  // Depend on presence (`hasSearch`), not the ReactNode identity — inline `search={<MenuSearch/>}`
  // changes every keystroke and would otherwise recreate this callback ref, stacking listeners.
  // The positioner's DOM mounts fresh each open; we also detach the listener when the ref clears.
  const hasSearch = search != null;
  const isOpen = React.useContext(MenuOpenContext);
  const searchResetRef = React.useRef<(() => void) | null>(null);
  const wasOpenRef = React.useRef(isOpen);
  // `MenuSearch` unmounts with the portal, so clear-on-close cannot live in its effect cleanup
  // (Strict Mode remounts would wipe a live query). Fire when open actually goes false instead.
  React.useEffect(() => {
    if (wasOpenRef.current && !isOpen) searchResetRef.current?.();
    wasOpenRef.current = isOpen;
  }, [isOpen]);
  const focusSearchCleanupRef = React.useRef<(() => void) | null>(null);
  const focusSearch = React.useCallback(
    (positioner: HTMLElement | null) => {
      focusSearchCleanupRef.current?.();
      focusSearchCleanupRef.current = null;
      if (!positioner || !hasSearch) return;
      const field = () => positioner.querySelector<HTMLInputElement>("input:not([type='hidden'])");
      // The first focus to land on the popup or inside it settles the hand-off, and spends it
      // either way: the popup element itself is Base UI's initial focus, so the field takes it; a
      // row means the menu was opened from the keyboard (deliberate list intent) and the field must
      // not take it. Spending it on a row is the point — Base UI re-focuses the popup element when
      // the pointer leaves the list while focus is inside it (floating-ui's list navigation, with
      // `highlightItemOnHover`/`resetOnPointerLeave` both on by default), and a still-armed redirect
      // would answer that by yanking focus off the row the user was on.
      const settle = (target: Element | null) => {
        const menu = positioner.querySelector<HTMLElement>('[role="menu"]');
        // `contains` counts the popup itself, so one check covers both cases.
        if (!menu || !target || !menu.contains(target)) return;
        cleanup();
        if (target === menu) field()?.focus();
      };
      const onFocusIn = (event: FocusEvent) => {
        settle(event.target instanceof Element ? event.target : null);
      };
      const cleanup = () => {
        positioner.removeEventListener("focusin", onFocusIn);
        if (focusSearchCleanupRef.current === cleanup) focusSearchCleanupRef.current = null;
      };
      positioner.addEventListener("focusin", onFocusIn);
      focusSearchCleanupRef.current = cleanup;
      requestAnimationFrame(() => {
        if (!positioner.isConnected) {
          cleanup();
          return;
        }
        // Base UI may have focused the popup (or a row) before the listener attached.
        settle(document.activeElement);
      });
    },
    [hasSearch],
  );

  return (
    <MenuSearchResetContext.Provider value={searchResetRef}>
      <BaseMenu.Portal render={<Portal />}>
        <BaseMenu.Positioner
          side={side}
          sideOffset={sideOffset}
          align={align}
          alignOffset={alignOffset}
          collisionPadding={collisionPadding}
          collisionBoundary={collisionBoundary}
          collisionAvoidance={collisionAvoidance}
          sticky={sticky}
          positionMethod={positionMethod}
          anchor={anchor}
          disableAnchorTracking={disableAnchorTracking}
          ref={focusSearch}
          render={<Positioner />}
        >
          <OverlayPanel
            elevation="overlay"
            radius="lg"
            sizing={sizing}
            header={search}
            footer={footer}
          >
            <BaseMenu.Popup {...props} render={<MenuPopup elevation="flat" />}>
              {children}
            </BaseMenu.Popup>
          </OverlayPanel>
        </BaseMenu.Positioner>
      </BaseMenu.Portal>
    </MenuSearchResetContext.Provider>
  );
}
