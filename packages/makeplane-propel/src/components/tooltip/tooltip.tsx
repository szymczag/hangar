import { Tooltip as BaseTooltip } from "@base-ui/react/tooltip";
import type { TooltipRoot } from "@base-ui/react/tooltip";
import * as React from "react";

import { TooltipArrow, TooltipPopup, type TooltipLayout } from "../../elements/tooltip";
import { Positioner } from "../../internal/positioner";
import { Shortcut } from "../shortcut";

export type { TooltipLayout };

export type TooltipProps<Payload = unknown> = Omit<
  TooltipRoot.Props<Payload>,
  "children" | "className" | "label" | "style" | "disabled"
> & {
  /**
   * The text shown inside the tooltip popup. `null` / `undefined` / `""` (or whitespace-only)
   * unmounts the popup itself (children still render, unaffected) — use this instead of `label={x
   * ?? ""}` for copy that may be missing (an email, a name).
   */
  label: string | null | undefined;
  /**
   * When `true`, no popup ever mounts for this trigger — not merely closed. Use this for a boolean
   * gate (e.g. only show a hint while a sidebar is collapsed). Passing Base UI's own `disabled`
   * directly still leaves the popup markup mounted (just visually closed), so it doesn't give the
   * same guarantee on its own — this prop drives that same Base UI `disabled` internally _and_
   * gates the popup markup.
   *
   * @default false
   */
  disabled?: boolean;
  /**
   * Optional keyboard-shortcut hint, dimmed (e.g. `"⌘ K"`). Sits inline-end of `label` when
   * `layout="single"`, or beneath it when `layout="stacked"`. Maps to the Figma "Cmd + K" slot —
   * omit it for a plain tooltip. This is visual text; put the canonical `aria-keyshortcuts` value
   * on the trigger element.
   */
  shortcut?: string;
  /**
   * Content arrangement. `single` is the compact Figma chip and wraps long labels within 500px;
   * `stacked` is the multiline description layout (body type, larger radius, 500px maximum width,
   * shortcut below). Longer content belongs in a popover.
   *
   * @default "single"
   */
  layout?: TooltipLayout;
  /**
   * The element the tooltip is attached to. Base UI renders the trigger as a `<button>` by default;
   * pass a single element and it is used as the trigger via the `render` prop, so any focusable
   * element (a real button, an icon button) can anchor the tooltip. Give the element an `id` when
   * using `createTooltipHandle` — `handle.open(id)` looks up that trigger id (a no-op while the
   * tooltip is gated off by `disabled` or a missing label — no popup mounts to open). Custom
   * components must forward the ref, event handlers, and aria attributes to the same DOM element.
   * The description is attached only while the popup is mounted; existing descriptions are
   * preserved.
   */
  children: React.ReactElement;
  /**
   * Which side of the trigger to place the popup on. May flip automatically to stay in view.
   *
   * @default "top"
   */
  side?: BaseTooltip.Positioner.Props["side"];
  /**
   * Gap in pixels between the trigger and the popup. Increase when using `showArrow` so the caret
   * has room between the trigger and the surface.
   *
   * @default 8
   */
  sideOffset?: number;
  /**
   * Alignment of the popup relative to the trigger along `side`.
   *
   * @default "center"
   */
  align?: BaseTooltip.Positioner.Props["align"];
  /**
   * Additional offset in px along the align axis — slides the popup along the trigger's edge
   * without changing `align`.
   *
   * @default 0
   */
  alignOffset?: BaseTooltip.Positioner.Props["alignOffset"];
  /**
   * Minimum gap in px between the popup and the viewport edge it would otherwise touch.
   *
   * @default 5
   */
  collisionPadding?: BaseTooltip.Positioner.Props["collisionPadding"];
  /**
   * The element or rect the popup is confined to when avoiding collisions. Base UI's clipping
   * ancestors when unset.
   */
  collisionBoundary?: BaseTooltip.Positioner.Props["collisionBoundary"];
  /**
   * What to do when the popup would overflow the boundary, set per axis: flip to the other side,
   * shift along it, or stay put. Base UI flips the side and shifts the alignment when unset.
   */
  collisionAvoidance?: BaseTooltip.Positioner.Props["collisionAvoidance"];
  /**
   * Render the caret pointing back at the trigger. Off by default — the Figma tooltip is a flat
   * surface with no built-in caret.
   *
   * @default false
   */
  showArrow?: boolean;
  /**
   * Minimum distance in px between the arrow and the popup's rounded corners. Ignored when
   * `showArrow` is false.
   *
   * @default 5
   */
  arrowPadding?: BaseTooltip.Positioner.Props["arrowPadding"];
  /**
   * Keep the popup on screen after the trigger scrolls out of view, instead of following it out.
   * Base UI may still set `data-anchor-hidden` when the anchor is clipped — that attribute is
   * independent of `sticky`. When `sticky` is false (default), this tooltip's positioner opts into
   * `hideWhenAnchorHidden` so `data-anchor-hidden` makes the tip `invisible` and it does not
   * linger. When `sticky` is true, the positioner stays visible even if the anchor is marked
   * hidden.
   *
   * @default false
   */
  sticky?: BaseTooltip.Positioner.Props["sticky"];
  /**
   * Which CSS `position` the positioner uses. `fixed` escapes overflow-clipping ancestors, e.g. a
   * trigger inside a sticky header.
   *
   * @default "absolute"
   */
  positionMethod?: BaseTooltip.Positioner.Props["positionMethod"];
  /**
   * Position against this element instead of the trigger — an element, a ref, a virtual element, or
   * a function returning one (e.g. a chart's pointer position). Geometry only; hover and focus stay
   * on the trigger.
   */
  anchor?: BaseTooltip.Positioner.Props["anchor"];
  /**
   * Stop tracking layout shifts of the anchor — position once, on open.
   *
   * @default false
   */
  disableAnchorTracking?: BaseTooltip.Positioner.Props["disableAnchorTracking"];
  /**
   * How long to wait (ms) before opening on hover. Focus opens immediately. Defaults to propel's
   * own `300` rather than Base UI's `600`, which read as a stall on hints people hover
   * deliberately. Because that default is always passed, a wrapping `TooltipProvider`'s `delay`
   * does not reach a ready-made `Tooltip` — set the timing here instead. Close timing is not on
   * this prop: use the provider's `closeDelay` (and shared grouping) when adjacent tooltips should
   * linger or swap without restarting the open delay.
   *
   * @default 300
   */
  delay?: number;
};

/**
 * A small popup that describes the element it is attached to. Appears on hover or keyboard focus of
 * the trigger and is dismissed on blur, pointer-leave, or `Esc`.
 *
 * Built on Base UI's tooltip, so it's accessible by default: the popup is exposed as
 * `role="tooltip"` and wired to the trigger. Pass the trigger as `children`, the popup copy as
 * `label`, and an optional `shortcut` for a dimmed visual keyboard hint.
 *
 * Grafts Base UI's tooltip behavior onto propel's styled parts: `Tooltip.Root` + `Tooltip.Trigger`
 * + `Tooltip.Portal` → `Tooltip.Positioner` (shared `internal/positioner`) → `TooltipPopup`, with
 * an optional `TooltipArrow` when `showArrow` is set. Colors come from propel's adaptive surface
 * tokens (`bg-layer-2` / `text-primary` / `border-subtle-1`), so the tooltip is light on light
 * themes and dark on dark themes, matching the Figma "Tooltip" component.
 */
export function Tooltip<Payload = unknown>({
  label,
  disabled = false,
  shortcut,
  layout = "single",
  children,
  side = "top",
  sideOffset = 8,
  align,
  alignOffset,
  collisionPadding,
  collisionBoundary,
  collisionAvoidance,
  showArrow = false,
  arrowPadding,
  sticky,
  positionMethod,
  anchor,
  disableAnchorTracking,
  // Baked rather than left to Base UI's `delay ?? providerDelay ?? 600`, so every ready-made
  // tooltip in the library opens at the same speed whether or not a `TooltipProvider` wraps it.
  // The cost is that a provider's `delay` no longer reaches a ready-made (a defined value always
  // wins); `closeDelay` and the group's instant swap are unaffected and still come from there.
  delay = 300,
  ...props
}: TooltipProps<Payload>) {
  const popupId = React.useId();
  const [popupMounted, setPopupMounted] = React.useState(false);
  const popupRef = React.useCallback((node: HTMLElement | null) => {
    setPopupMounted(node !== null);
  }, []);

  // Gate on `disabled`/`label`, but keep the same tree shape (`Root` + `Trigger`) either way —
  // swapping shapes on toggle would force React to tear down and recreate the trigger's DOM node,
  // dropping focus. Base UI's own `disabled` closes the popup and reports the closed state through
  // `onOpenChange` for a controlled consumer (a plain unmount never would); only the popup markup
  // below is conditional, so no popup markup mounts while gated off. Whitespace-only labels count
  // as missing so they never mount a blank-looking popup (the raw `label` still renders when
  // mounted).
  const mounted = !disabled && !!label?.trim();

  // Base UI registers the trigger under this id for `createTooltipHandle().open(triggerId)`.
  // The ready-made Trigger does not take consumer props itself, so lift `id` off `children`.
  const triggerId =
    typeof (children.props as { id?: unknown }).id === "string"
      ? (children.props as { id: string }).id
      : undefined;

  const existingDescription = (children.props as { "aria-describedby"?: string })[
    "aria-describedby"
  ];
  const accessibleName = (children.props as { "aria-label"?: unknown })["aria-label"];
  const repeatsName = typeof accessibleName === "string" && accessibleName.trim() === label?.trim();
  const describedBy =
    [existingDescription, popupMounted && !repeatsName ? popupId : undefined]
      .filter(Boolean)
      .join(" ") || undefined;

  return (
    <BaseTooltip.Root {...props} disabled={!mounted}>
      <BaseTooltip.Trigger
        id={triggerId}
        delay={delay}
        render={React.cloneElement(
          children as React.ReactElement<React.HTMLAttributes<HTMLElement>>,
          { "aria-describedby": describedBy },
        )}
      />
      {mounted ? (
        <BaseTooltip.Portal>
          <BaseTooltip.Positioner
            side={side}
            sideOffset={sideOffset}
            align={align}
            alignOffset={alignOffset}
            collisionPadding={collisionPadding}
            collisionBoundary={collisionBoundary}
            collisionAvoidance={collisionAvoidance}
            arrowPadding={arrowPadding}
            sticky={sticky}
            positionMethod={positionMethod}
            anchor={anchor}
            disableAnchorTracking={disableAnchorTracking}
            render={<Positioner hideWhenAnchorHidden={!sticky} />}
          >
            {/* Link the popup explicitly: Base UI supplies interaction behavior but does not
                attach an accessible description. Preserve descriptions already on the trigger. */}
            <BaseTooltip.Popup
              ref={popupRef}
              id={popupId}
              role="tooltip"
              render={<TooltipPopup layout={layout} />}
            >
              {label}
              {shortcut ? <Shortcut keys={shortcut} size="sm" /> : null}
              {showArrow ? <BaseTooltip.Arrow render={<TooltipArrow />} /> : null}
            </BaseTooltip.Popup>
          </BaseTooltip.Positioner>
        </BaseTooltip.Portal>
      ) : null}
    </BaseTooltip.Root>
  );
}
