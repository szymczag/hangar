import { Drawer as BaseDrawer } from "@base-ui/react/drawer";
import * as React from "react";

import {
  DrawerContent,
  DrawerInlineHost,
  DrawerInlinePortal,
  DrawerPopup,
  type DrawerPopupSide,
  type DrawerPopupSize,
  type DrawerPopupVariant,
  DrawerViewport,
} from "../../elements/drawer";
import { DrawerBackdrop } from "./drawer-backdrop";

export type DrawerPanelVariant = DrawerPopupVariant;

type DrawerPortalContainer = NonNullable<BaseDrawer.Portal.Props["container"]>;

type DrawerPanelSharedProps = Omit<
  BaseDrawer.Popup.Props,
  "className" | "style" | "render" | "children"
> & {
  /**
   * The viewport edge the drawer is anchored to. "end" pins to the inline-end (right in LTR);
   * "start" pins to the inline-start (left in LTR). The slide animation direction and the
   * leading-edge chrome both follow this value. Pair with `Drawer` `swipeDirection`: `"end"` →
   * `"right"`, `"start"` → `"left"`.
   */
  side: DrawerPopupSide;
  /**
   * Panel width: `sm` 358px, `md` 800px, `lg` 1024px. Prefer `sm` with `inline`; `md` / `lg` with
   * `overlay` / `contained`.
   *
   * @default "sm"
   */
  size?: DrawerPopupSize;
  /** The panel body — typically a `DrawerHeader`, `DrawerBody`, and `DrawerFooter`. */
  children?: React.ReactNode;
};

/**
 * Placement + chrome:
 *
 * - `inline` — flush edge column absolutely positioned inside a `relative` parent. Does not push
 *   siblings. Prefer `size="sm"`. Pass `container` to portal into a specific positioned shell;
 *   otherwise an auto host fills the nearest positioned ancestor. No backdrop.
 * - `contained` — floating card portaled into `container` (required) — e.g. main shell under a search
 *   topnav. Absolute inside that shell; does not cover outer chrome. No backdrop (use `overlay`
 *   when you need a page scrim).
 * - `overlay` — floating card portaled to `document.body` (viewport-fixed). Prefer `md` / `lg`.
 *   Opt-in `backdrop` for a viewport-fixed scrim.
 */
export type DrawerPanelProps =
  | (DrawerPanelSharedProps & {
      /**
       * Placement + chrome. Defaults to the flush absolute column (`inline`).
       *
       * @default "inline"
       */
      variant?: "inline";
      /**
       * Portal target. When omitted, uses an absolute-fill host (parent must be `relative`). Pass a
       * positioned shell when you manage the host yourself.
       */
      container?: BaseDrawer.Portal.Props["container"];
    })
  | (DrawerPanelSharedProps & {
      /** Floating card portaled to `document.body` (viewport-fixed). Prefer `md` / `lg`. */
      variant: "overlay";
      /**
       * When true, mounts a dimmed viewport-fixed `DrawerBackdrop`. Only available on `overlay`
       * (pair with `<Drawer modal>`).
       *
       * @default false
       */
      backdrop?: boolean;
      /** Portal target. When omitted, uses `document.body`. */
      container?: BaseDrawer.Portal.Props["container"];
    })
  | (DrawerPanelSharedProps & {
      /** Floating card portaled into a positioned parent shell (`container` required). */
      variant: "contained";
      /** Positioned parent the floating card portals into (required for `contained`). */
      container: DrawerPortalContainer;
    });

/**
 * Convenience that composes drawer portal/viewport/popup boilerplate. Defaults to `inline` + `sm`
 * (flush absolute column in a relative parent). `overlay` portals to `document.body`; `contained`
 * requires a parent `container`. `backdrop` is overlay-only.
 */
export function DrawerPanel(props: DrawerPanelProps) {
  // `backdrop` exists only on the overlay branch; widen so we can strip it from Popup props.
  const {
    variant = "inline",
    container,
    side,
    size = "sm",
    children,
    backdrop: backdropProp,
    ...popupProps
  } = props as DrawerPanelProps & { backdrop?: boolean };
  const backdrop = variant === "overlay" && Boolean(backdropProp);
  const [inlineHost, setInlineHost] = React.useState<HTMLDivElement | null>(null);

  const panel = (
    <>
      {backdrop ? <DrawerBackdrop /> : null}
      <BaseDrawer.Viewport render={<DrawerViewport variant={variant} />}>
        <BaseDrawer.Popup
          {...popupProps}
          render={<DrawerPopup variant={variant} side={side} size={size} />}
        >
          <BaseDrawer.Content render={<DrawerContent size={size} />}>{children}</BaseDrawer.Content>
        </BaseDrawer.Popup>
      </BaseDrawer.Viewport>
    </>
  );

  if (variant === "inline" && container == null) {
    return (
      <>
        <DrawerInlineHost ref={setInlineHost} />
        {inlineHost ? (
          <BaseDrawer.Portal container={inlineHost} render={<DrawerInlinePortal />}>
            {panel}
          </BaseDrawer.Portal>
        ) : null}
      </>
    );
  }

  if (variant === "inline") {
    return (
      <BaseDrawer.Portal container={container} render={<DrawerInlinePortal />}>
        {panel}
      </BaseDrawer.Portal>
    );
  }

  return <BaseDrawer.Portal container={container}>{panel}</BaseDrawer.Portal>;
}
